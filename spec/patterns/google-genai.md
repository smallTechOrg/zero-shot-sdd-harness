# Usage-spec: google-genai (Gemini)

**Version: `google-genai` 1.x** (verify latest before pinning — a bump REFRESHES this file)
**Stamped: 2026-06 · the unified Google GenAI SDK; supersedes the deprecated `google-generativeai`.**

Guards: `model-and-providers.md` (`agent/llm.py`) when the spec pins **Gemini** as the provider. The core
relies on exactly these shapes; a model trained on the old SDK will hallucinate the deprecated one.

## ⚠️ The package is `google-genai`, NOT `google-generativeai` (C-LLM-SDK)
```python
from google import genai
from google.genai import types
```
- ✅ pip-install **`google-genai`**; import **`from google import genai`** (note: the `google` namespace,
  the `genai` submodule). This is the unified, current SDK.
- ❌ Do NOT `pip install google-generativeai` / `import google.generativeai as genai` — that is the
  **deprecated** legacy SDK (`genai.configure(...)` / `genai.GenerativeModel(...)`). It is frozen, its API
  shape differs, and pinning it is the canonical Gemini hallucination (`C-LLM-SDK`). Training data is full of
  it — do not trust the model here, trust this file.

## Client + call shape (the one accessor the core relies on)
```python
client = genai.Client(api_key=key)            # key from settings.llm_api_key.get_secret_value()
resp = client.models.generate_content(
    model="gemini-2.5-flash",                 # ← from config, NEVER hardcoded — see lifecycle below
    contents=prompt,                          # str, or a list of parts/Content for multimodal/multi-turn
    config=types.GenerateContentConfig(
        system_instruction=system,            # the system prompt goes HERE, not in contents
        temperature=0,
    ),
)
text = resp.text                              # the convenience accessor — the concatenated text
```
- ✅ `genai.Client(api_key=...)` once, reuse it; call `client.models.generate_content(...)`.
- ✅ The **system prompt** is `config.system_instruction`, not a message in `contents` (no "system role" in
  `contents` the way other providers have).
- ✅ Read `resp.text` for the text. ❌ Don't reach into `resp.candidates[0].content.parts[0].text` unless you
  genuinely need part-level access — `resp.text` is the supported convenience path.
- ⚠️ `resp.text` can be `None` (e.g. a safety block or a finish reason of `MAX_TOKENS` with no text part) —
  coerce: `text = resp.text or ""` before string ops, same as the langchain-core content-coerce rule.

## ⚠️ Markdown-fence stripping (C-LLM-FENCE)
Gemini **wraps JSON in a ` ```json ` markdown fence even when explicitly told to return raw JSON** — so
`json.loads(resp.text)` raises `JSONDecodeError` on the leading ` ```json` line. The build stays green (no
live call in unit tests) and the **real run fails to parse**. Strip the fence before `json.loads`:
```python
def _strip_fences(text: str) -> str:
    """Remove a leading ```json / ``` fence and a trailing ``` fence, if present."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]                          # drop the opening ```json (or ```) line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]                     # drop the closing ``` line
        t = "\n".join(lines).strip()
    return t
# ... usage:  data = json.loads(_strip_fences(resp.text or ""))
```
- ✅ Strip on the **fence**, tolerant of ` ```json ` *or* a bare ` ``` ` opener, and of a missing closer.
- ❌ Don't `json.loads(resp.text)` directly when you asked for JSON — it will intermittently 500.

## Model lifecycle — the model name lives in config, NEVER hardcoded
Gemini model ids go **stale fast**. The pinned field moved across 2025–2026:
`gemini-1.5-flash` → `gemini-2.0-flash` → `gemini-2.5-flash` → `gemini-3.1-flash-lite`. A hardcoded id is a
time-bomb 404.
- ✅ Keep the model id in `agent/config.py` (`APP_LLM_MODEL`, a `pydantic-settings.md` field) and read it at
  call time. Flip the model with **config only — no code change** (same rule as `C-PROD-DRIVER`).
- ✅ **Verify the current id at build time** before pinning — check the **`claude-api` skill** for the
  provider-id conventions and the live Google Gemini model docs to confirm what is current; do not pin from
  this file's example (it WILL be stale). The default in config is a sane current id, not a literal in code.
- The drift-auditor flags a pinned model id that no longer matches a live model — refresh config + this file
  together when it moves.

## `GeminiClient.complete(prompt, system)` — the reference implementation
```python
import json
from google import genai
from google.genai import types

class GeminiClient:
    def __init__(self, api_key: str, model: str):     # model from config — NOT hardcoded
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, system: str | None = None) -> str:
        resp = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0),
        )
        return _strip_fences(resp.text or "")          # fence-strip so json.loads works downstream
```
- ✅ Provider-as-config: only this client touches `genai` (`C-LLM-ACCESSOR`); nodes call `complete(...)`.
- ✅ `api_key` arrives unwrapped from `SecretStr.get_secret_value()` at this one boundary
  (`pydantic-settings.md` C-SECRET-TYPE) — never log it.
