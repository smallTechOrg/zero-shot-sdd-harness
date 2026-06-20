import ast
import re
from contextvars import ContextVar
from dataclasses import dataclass
from .observability import span


PII = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "ssn":   re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "card":  re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "phone": re.compile(r"\b\+?\d[\d -]{7,}\d\b"),
}
STRATEGY = {"email": "mask", "ssn": "hash", "card": "block", "phone": "redact"}


def _mask(s: str) -> str:
    return s[0] + "***" + s[-4:] if len(s) > 5 else "***"


def _hash(s: str) -> str:
    import hashlib
    return "pii_" + hashlib.sha256(s.encode()).hexdigest()[:12]


@dataclass
class Verdict:
    action: str
    payload: str
    reason: str = ""


def scan_pii(text: object) -> Verdict:
    if isinstance(text, list):
        text = "\n".join(p["text"] for p in text if isinstance(p, dict) and p.get("type") == "text") or str(text)
    elif not isinstance(text, str):
        text = str(text)
    found, out, blocked = [], text, False
    for kind, rx in PII.items():
        if not rx.search(out):
            continue
        found.append(kind)
        strat = STRATEGY.get(kind, "redact")
        if strat == "block":
            blocked = True
        elif strat == "mask":
            out = rx.sub(lambda m: _mask(m.group()), out)
        elif strat == "hash":
            out = rx.sub(lambda m: _hash(m.group()), out)
        else:
            out = rx.sub(f"[REDACTED_{kind.upper()}]", out)
    if blocked:
        return Verdict("block", "", f"blocked PII: {','.join(found)}")
    if found:
        return Verdict("transform", out, f"redacted PII: {','.join(found)}")
    return Verdict("allow", text)


# --- AST-validated safe eval (C-ACTION-SAFETY) ---

SAFE_BUILTINS = {"abs": abs, "min": min, "max": max, "sum": sum, "len": len,
                 "round": round, "sorted": sorted, "list": list, "dict": dict,
                 "str": str, "int": int, "float": float, "bool": bool, "type": type}
ALLOWED_NAMES = frozenset(SAFE_BUILTINS) | frozenset({"df", "pd", "np"})
BLOCKED_ATTRS = frozenset({
    "__class__", "__bases__", "__mro__", "__subclasses__", "__globals__", "__builtins__",
    "__import__", "__dict__", "__getattribute__", "eval", "exec", "compile", "open",
    "os", "sys", "subprocess", "socket", "input",
})
ALLOWED_NODES = (
    ast.Expression, ast.Call, ast.Attribute, ast.Name, ast.Load, ast.Constant,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Subscript, ast.Slice,
    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.keyword,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv,
    ast.USub, ast.UAdd, ast.And, ast.Or, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.IfExp,
)


def safe_eval(expr: str, names: dict):
    """Validate then evaluate an LLM-generated expression. Raises ValueError on anything unsafe."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"unparseable expression: {e}")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Attribute) and node.attr in BLOCKED_ATTRS:
            raise ValueError(f"blocked attribute: {node.attr}")
        if isinstance(node, ast.Name):
            if node.id in BLOCKED_ATTRS:
                raise ValueError(f"blocked name: {node.id}")
            if node.id not in ALLOWED_NAMES and node.id not in names:
                raise ValueError(f"name not in allowlist: {node.id}")
    ns = {**SAFE_BUILTINS, **names}
    return eval(compile(tree, "<safe_eval>", "eval"), {"__builtins__": {}}, ns)


# --- Guardrail hooks ---

async def on_input(run_id: str, goal: str, policy: str = "") -> Verdict:
    async with span(run_id, "guardrail.on_input", "INTERNAL") as sp:
        v = scan_pii(goal)
        sp["action"], sp["reason"] = v.action, v.reason
        return v


async def on_tool_call(run_id: str, name: str, args: dict) -> Verdict:
    async with span(run_id, f"guardrail.on_tool_call.{name}", "INTERNAL") as sp:
        v = scan_pii(str(args))
        sp["action"], sp["reason"] = v.action, v.reason
        return v


async def on_output(run_id: str, answer: str, policy: str = "") -> Verdict:
    async with span(run_id, "guardrail.on_output", "INTERNAL") as sp:
        v = scan_pii(answer)
        sp["action"], sp["reason"] = v.action, v.reason
        return v


# --- HITL: human-approval gate for sensitive / irreversible tools ---
hitl_approved: ContextVar[bool] = ContextVar("hitl_approved", default=False)
RISKY_TOOLS = frozenset({"delete_memories"})


def requires_approval(tool_name: str) -> bool:
    """A risky/irreversible tool is gated until a human approves this run (HITL)."""
    return tool_name in RISKY_TOOLS and not hitl_approved.get()
