import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from .config import validate_required_config
from .db import get_sessionmaker, init_db, Run, Span
from .runner import run_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_required_config()
    await init_db()
    yield


app = FastAPI(title="Grounded Assistant", lifespan=lifespan)


def ok(data):
    return {"ok": True, "data": data}


class ApiError(Exception):
    def __init__(self, code: str, msg: str = "", status: int = 500):
        self.code, self.msg, self.status = code, msg or code, status


def api_error(code: str, msg: str = "", status: int = 500) -> ApiError:
    return ApiError(code, msg, status)


@app.exception_handler(ApiError)
async def _api_error_handler(_req, exc: ApiError):
    return JSONResponse({"ok": False, "error": {"code": exc.code, "message": exc.msg}}, status_code=exc.status)


class RunIn(BaseModel):
    goal: str
    session_id: str | None = None
    data: str | None = None
    approve: bool = False        # human-in-the-loop: confirm a sensitive action on re-submit


@app.get("/health")
async def health():
    return ok({"status": "alive"})


@app.post("/runs")
async def create_run(request: Request, body: RunIn):
    try:
        if body.data is not None:
            from .sessions import load_resource
            if body.session_id is None:
                body.session_id = uuid.uuid4().hex
            load_resource(body.session_id, body.data)
        return ok(await run_agent(body.goal, session_id=body.session_id, approve=body.approve))
    except ApiError:
        raise
    except Exception as e:
        raise api_error("RUN_FAILED", str(e), status=500)


@app.get("/", response_class=HTMLResponse)
async def root():
    return _ui_html()


KIND_COLOR = {"INTERNAL": "#6b7280", "LLM": "#2563eb", "TOOL": "#16a34a"}
KIND_PLAIN = {"INTERNAL": "Run step", "LLM": "Asked the AI model", "TOOL": "Used a tool"}


def _esc(x) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _plain_step(sp) -> str:
    if sp.name.startswith("execute_tool."):
        return "Used a tool: " + sp.name.removeprefix("execute_tool.").replace("_", " ")
    if sp.kind == "LLM":
        return "Asked the AI model"
    if sp.name == "invoke_agent":
        return "Ran the agent"
    return KIND_PLAIN.get(sp.kind, sp.name)


def _ui_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Grounded Assistant</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #111; }
    h1 { margin-bottom: 0.25rem; }
    p.sub { color: #6b7280; margin-top: 0; }
    label { display: block; font-weight: 600; margin: 1rem 0 0.25rem; }
    textarea, input[type=text] { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; font-family: inherit; }
    textarea { resize: vertical; }
    button { margin-top: 12px; padding: 9px 24px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-size: 15px; cursor: pointer; }
    button:disabled { background: #93c5fd; cursor: default; }
    #result { margin-top: 1.5rem; display: none; }
    #answer { white-space: pre-wrap; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 1rem; min-height: 60px; font-size: 14px; }
    .meta { font-size: 12px; color: #9ca3af; margin-top: 6px; }
    .meta a { color: #6b7280; }
    .error { color: #dc2626; }
  </style>
</head>
<body>
  <h1>Grounded Assistant</h1>
  <p class="sub">Paste a document and ask questions — answered using only that document.</p>

  <label for="data-input">Document (paste text here):</label>
  <textarea id="data-input" aria-label="data" rows="7"
    placeholder="Paste a document here (a policy, FAQ, notes…), then ask a question about it."></textarea>

  <label for="goal-input">Question:</label>
  <input id="goal-input" aria-label="goal" type="text"
    placeholder="e.g. How many vacation days do employees get?">

  <button id="run-btn" onclick="run()">Run</button>

  <div id="result">
    <label>Answer:</label>
    <div data-testid="answer" id="answer"></div>
    <div class="meta" id="meta">
      <span id="stats"></span> &nbsp;·&nbsp;
      <a id="trace-link" href="/traces">trace</a> &nbsp;·&nbsp;
      <a href="/traces">all runs</a>
    </div>
  </div>

  <script>
    const SID_KEY = 'da_session_id';
    let sid = localStorage.getItem(SID_KEY) || crypto.randomUUID();
    localStorage.setItem(SID_KEY, sid);

    async function run() {
      const data = document.getElementById('data-input').value.trim();
      const goal = document.getElementById('goal-input').value.trim();
      if (!goal) { alert('Please enter a question.'); return; }

      const btn = document.getElementById('run-btn');
      btn.textContent = 'Running…'; btn.disabled = true;

      const body = { goal, session_id: sid };
      if (data) body.data = data;

      try {
        const res = await fetch('/runs', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        });
        const json = await res.json();
        document.getElementById('result').style.display = 'block';
        const answerEl = document.getElementById('answer');
        if (json.ok && json.data) {
          answerEl.textContent = json.data.answer || '(no answer)';
          answerEl.className = '';
          const d = json.data;
          const toks = (d.input_tokens || 0) + (d.output_tokens || 0);
          document.getElementById('stats').textContent =
            toks.toLocaleString() + ' tokens · $' + (d.cost_usd || 0).toFixed(4) + ' · ' + (d.iterations || 0) + ' steps';
        } else {
          answerEl.textContent = 'Error: ' + (json.error?.message || JSON.stringify(json));
          answerEl.className = 'error';
        }
      } catch (e) {
        document.getElementById('result').style.display = 'block';
        document.getElementById('answer').textContent = 'Network error: ' + e.message;
        document.getElementById('answer').className = 'error';
      } finally {
        btn.textContent = 'Run'; btn.disabled = false;
      }
    }

    document.getElementById('goal-input').addEventListener('keydown', e => {
      if (e.key === 'Enter') run();
    });
  </script>
</body>
</html>"""


async def _traces_html() -> str:
    async with get_sessionmaker()() as s:
        runs = (await s.execute(select(Run).order_by(Run.created_at.desc()))).scalars().all()
        spans = (await s.execute(select(Span).order_by(Span.start_ms))).scalars().all()
    by_run: dict[str, list] = {}
    for sp in spans:
        by_run.setdefault(sp.run_id, []).append(sp)

    total = len(runs)
    ok_runs = sum(1 for r in runs if r.status == "completed")
    total_cost = sum(r.cost_usd or 0 for r in runs)
    total_tokens = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in runs)

    def _run_ms(rid):
        sp = by_run.get(rid) or []
        return max((s.end_ms - s.start_ms for s in sp), default=0)

    avg_ms = (sum(_run_ms(r.id) for r in runs) / total) if total else 0

    def _card(label, value):
        return (f"<div style='flex:1;min-width:120px;background:#f9fafb;border:1px solid #e5e7eb;"
                f"border-radius:8px;padding:12px'><div style='font-size:22px;font-weight:700'>{value}</div>"
                f"<div style='color:#6b7280;font-size:13px'>{_esc(label)}</div></div>")

    overview = (
        "<div style='display:flex;gap:12px;flex-wrap:wrap;margin:0 0 24px'>"
        + _card("runs", total)
        + _card("succeeded", f"{ok_runs}/{total}" + (f" ({100*ok_runs//total}%)" if total else ""))
        + _card("total cost", f"${total_cost:.4f}")
        + _card("avg cost / run", f"${(total_cost/total if total else 0):.4f}")
        + _card("total tokens", f"{total_tokens:,}")
        + _card("avg answer time", f"{avg_ms/1000:.1f}s")
        + "</div>"
    )

    rows = []
    for r in runs:
        rspans = by_run.get(r.id, [])
        maxd = max((sp.duration_ms for sp in rspans), default=1) or 1
        badge = "#16a34a" if r.status == "completed" else "#dc2626" if r.status == "error" else "#d97706"
        meta = (f"<span style='color:{badge};font-weight:600'>{_esc(r.status)}</span> · "
                f"{len(rspans)} steps · ${r.cost_usd or 0:.4f} · "
                f"{(r.input_tokens or 0)+(r.output_tokens or 0):,} tokens")
        steps = []
        for sp in rspans:
            color = KIND_COLOR.get(sp.kind, "#6b7280")
            bar = max(2, int(200 * sp.duration_ms / maxd))
            err_attr = sp.attributes.get("error") if isinstance(sp.attributes, dict) else None
            err_html = f"<div style='color:#dc2626;margin-left:8px'>&#9888; {_esc(err_attr)}</div>" if err_attr else ""
            steps.append(
                f"<div style='margin:4px 0'>"
                f"<b>{_esc(_plain_step(sp))}</b> "
                f"<span style='display:inline-block;height:8px;width:{bar}px;background:{color};vertical-align:middle'></span> "
                f"<span style='color:#6b7280'>{sp.duration_ms/1000:.2f}s</span> "
                f"<span style='color:#9ca3af;font-size:12px'>{_esc(sp.name)}</span>"
                f"<pre style='margin:2px 0 2px 8px;color:#374151;font-size:12px;white-space:pre-wrap'>{_esc(sp.attributes)}</pre>"
                f"{err_html}</div>"
            )
        rows.append(
            f"<details id='{_esc(r.id)}' style='border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin:0 0 12px'"
            f"{' open' if r is runs[0] else ''}>"
            f"<summary style='cursor:pointer'><b>{_esc(r.goal)}</b> "
            f"<span style='color:#9ca3af;font-size:12px;font-weight:400'>{_esc(r.id)}</span>"
            f"<br><small>{meta}</small></summary>"
            f"<div style='margin-top:8px'>{''.join(steps) or '<i>no steps recorded</i>'}</div></details>"
        )
    body = overview + ("".join(rows) or "<p>No runs yet. POST a goal to /runs.</p>")
    return (f"<html><body style='font-family:system-ui;max-width:900px;margin:2rem auto'>"
            f"<h1>Observability dashboard</h1>"
            f"<p style='color:#6b7280'>Every run the agent did, in plain English.</p>"
            f"{body}</body></html>")


@app.get("/traces", response_class=HTMLResponse)
async def traces():
    return await _traces_html()
