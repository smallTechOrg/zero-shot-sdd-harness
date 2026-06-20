import json
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from .config import validate_required_config
from .db import get_sessionmaker, init_db, Run, Span
from .runner import run_agent, stream_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_required_config()
    await init_db()
    yield


app = FastAPI(title="Data Analyst", lifespan=lifespan)


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


@app.post("/runs/stream")
async def stream_run(body: RunIn):
    async def gen():
        try:
            if body.data is not None:
                from .sessions import load_resource
                if body.session_id is None:
                    body.session_id = uuid.uuid4().hex
                load_resource(body.session_id, body.data)
            async for ev in stream_agent(body.goal, session_id=body.session_id):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
  <title>Data Analyst</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #111; }
    h1 { margin-bottom: 0.25rem; }
    p.sub { color: #6b7280; margin-top: 0; margin-bottom: 1.5rem; }
    .upload-zone { border: 2px dashed #d1d5db; border-radius: 8px; padding: 1.5rem; text-align: center; cursor: pointer; transition: border-color .2s; margin-bottom: 1rem; }
    .upload-zone:hover, .upload-zone.drag { border-color: #2563eb; background: #eff6ff; }
    .upload-zone input { display: none; }
    .upload-zone.loaded { border-color: #16a34a; background: #f0fdf4; }
    label.field { display: block; font-weight: 600; margin: 0.75rem 0 0.25rem; }
    input[type=text] { width: 100%; padding: 9px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; font-family: inherit; }
    .row { display: flex; gap: 8px; margin-top: 10px; }
    button { padding: 9px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; font-family: inherit; }
    #run-btn { background: #2563eb; color: #fff; flex: 1; }
    #run-btn:disabled { background: #93c5fd; cursor: default; }
    #clear-btn { background: #f3f4f6; color: #374151; }
    #chat { margin-top: 1.5rem; }
    .turn { margin-bottom: 1.5rem; }
    .turn .q { font-weight: 600; color: #374151; margin-bottom: 6px; }
    .turn .a { white-space: pre-wrap; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 1rem; font-size: 14px; font-family: monospace; }
    .turn .chart-wrap { margin-top: 12px; max-height: 360px; }
    .turn .meta { font-size: 12px; color: #9ca3af; margin-top: 6px; }
    .turn .meta a { color: #6b7280; }
    .error { color: #dc2626; background: #fef2f2 !important; border-color: #fecaca !important; }
  </style>
</head>
<body>
  <h1>Data Analyst</h1>
  <p class="sub">Upload a CSV or JSON dataset, then ask questions in plain English.</p>

  <div class="upload-zone" id="drop-zone" onclick="document.getElementById('file-input').click()"
       ondragover="event.preventDefault();this.classList.add('drag')"
       ondragleave="this.classList.remove('drag')"
       ondrop="handleDrop(event)">
    <input type="file" id="file-input" accept=".csv,.json,.tsv" onchange="handleFile(this.files[0])">
    <span id="upload-label">&#128193; Drop a CSV / JSON file here, or click to browse</span>
  </div>

  <label class="field" for="goal-input">Ask a question:</label>
  <input id="goal-input" type="text" placeholder="e.g. What is the total revenue? Which month had the highest sales?">

  <div class="row">
    <button id="run-btn" onclick="run()">Analyse</button>
    <button id="clear-btn" onclick="newSession()">New session</button>
  </div>

  <div id="chat"></div>

  <script>
    const SID_KEY = 'analyst_session_id';
    let sid = localStorage.getItem(SID_KEY) || crypto.randomUUID();
    localStorage.setItem(SID_KEY, sid);
    let pendingData = null;
    let chartCount = 0;

    function handleFile(file) {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = e => {
        pendingData = e.target.result;
        const zone = document.getElementById('drop-zone');
        zone.classList.add('loaded');
        document.getElementById('upload-label').textContent = '✓ ' + file.name + ' ready';
      };
      reader.readAsText(file);
    }

    function handleDrop(e) {
      e.preventDefault();
      document.getElementById('drop-zone').classList.remove('drag');
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    }

    function newSession() {
      sid = crypto.randomUUID();
      localStorage.setItem(SID_KEY, sid);
      pendingData = null;
      document.getElementById('chat').innerHTML = '';
      document.getElementById('upload-label').textContent = '📁 Drop a CSV / JSON file here, or click to browse';
      document.getElementById('drop-zone').classList.remove('loaded');
    }

    async function run() {
      const goal = document.getElementById('goal-input').value.trim();
      if (!goal) { document.getElementById('goal-input').focus(); return; }
      const btn = document.getElementById('run-btn');
      btn.textContent = 'Analysing…'; btn.disabled = true;

      const body = { goal, session_id: sid };
      if (pendingData) { body.data = pendingData; pendingData = null; }

      const turn = document.createElement('div');
      turn.className = 'turn';
      turn.innerHTML = '<div class="q">Q: ' + escHtml(goal) + '</div><div class="a">…</div>';
      document.getElementById('chat').prepend(turn);
      document.getElementById('goal-input').value = '';

      try {
        const res = await fetch('/runs', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        });
        const json = await res.json();
        const aEl = turn.querySelector('.a');
        if (json.ok && json.data) {
          const d = json.data;
          aEl.textContent = d.answer || '(no answer)';
          aEl.className = 'a';
          if (d.chart) {
            try {
              const cfg = typeof d.chart === 'string' ? JSON.parse(d.chart) : d.chart;
              const wrap = document.createElement('div');
              wrap.className = 'chart-wrap';
              const canvas = document.createElement('canvas');
              canvas.id = 'chart-' + (++chartCount);
              wrap.appendChild(canvas);
              turn.appendChild(wrap);
              new Chart(canvas, cfg);
            } catch (e) { /* malformed chart JSON — skip silently */ }
          }
          const toks = (d.input_tokens || 0) + (d.output_tokens || 0);
          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.innerHTML = toks.toLocaleString() + ' tokens · $' + (d.cost_usd || 0).toFixed(4)
            + ' · ' + (d.iterations || 0) + ' steps &nbsp;·&nbsp; <a href="/traces">trace</a>';
          turn.appendChild(meta);
        } else {
          turn.querySelector('.a').textContent = 'Error: ' + (json.error?.message || JSON.stringify(json));
          turn.querySelector('.a').className = 'a error';
        }
      } catch (e) {
        turn.querySelector('.a').textContent = 'Network error: ' + e.message;
        turn.querySelector('.a').className = 'a error';
      } finally {
        btn.textContent = 'Analyse'; btn.disabled = false;
      }
    }

    function escHtml(s) {
      return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
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
