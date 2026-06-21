"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// [C-PLOTLY-SSR]: never import at top level — use dynamic with ssr:false
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const API = "/api";
const PAGE_SIZE = 50;

// ── helpers ────────────────────────────────────────────────────────────────

function genId() {
  // [C-SESSION-SCOPE]: crypto.randomUUID with Math.random fallback
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  } catch {}
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

// Safe localStorage — never throws, guards SSR
const ls = {
  get: (key) => { try { return window.localStorage.getItem(key); } catch { return null; } },
  set: (key, val) => { try { window.localStorage.setItem(key, val); } catch {} },
  remove: (key) => { try { window.localStorage.removeItem(key); } catch {} },
};

function getOrCreate(key, factory) {
  const v = ls.get(key);
  if (v) return v;
  const n = factory();
  ls.set(key, n);
  return n;
}

/** Detect if a string is a single scalar number */
function isScalar(text) {
  return /^\s*[\d,]+\.?\d*\s*$/.test(text ?? "");
}

/** Parse a GFM markdown table into { headers, rows } or null */
function parseMarkdownTable(text) {
  if (!text) return null;
  const lines = text.trim().split("\n");
  if (lines.length < 3) return null;
  // Check separator line (second line has dashes/pipes)
  if (!/^\|?[\s\-|:]+\|?$/.test(lines[1])) return null;
  const parseRow = (line) =>
    line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  const headers = parseRow(lines[0]);
  const rows = lines.slice(2).map(parseRow);
  return { headers, rows };
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[d.getMonth()]} ${d.getDate()}, ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
}

// ── StubBanner ─────────────────────────────────────────────────────────────

function StubBanner({ stubMode }) {
  if (!stubMode) return null;
  return (
    <div className="bg-yellow-100 border-b border-yellow-300 text-yellow-800 text-sm px-4 py-2 flex items-center gap-2">
      <span>⚠</span>
      <span>
        Running in stub mode — LLM responses are simulated. Set{" "}
        <code className="bg-yellow-200 px-1 rounded">APP_LLM_API_KEY</code> to enable real AI.
      </span>
    </div>
  );
}

// ── DataTable ──────────────────────────────────────────────────────────────

function DataTable({ headers, rows }) {
  const [page, setPage] = useState(0);
  const totalPages = Math.ceil(rows.length / PAGE_SIZE);
  const start = page * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, rows.length);
  const visible = rows.slice(start, end);

  return (
    <div className="mt-2 overflow-x-auto">
      <table className="text-xs border-collapse w-full">
        <thead>
          <tr className="bg-gray-100">
            {headers.map((h, i) => (
              <th key={i} className="border border-gray-300 px-2 py-1 text-left font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? "bg-white" : "bg-gray-50"}>
              {row.map((cell, ci) => (
                <td key={ci} className="border border-gray-300 px-2 py-1">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > PAGE_SIZE && (
        <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
          >
            Prev
          </button>
          <span>
            Showing {start + 1}–{end} of {rows.length} rows
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page === totalPages - 1}
            className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-100"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// ── PlotlyChart ────────────────────────────────────────────────────────────

function PlotlyChart({ spec }) {
  if (!spec) return null;
  const { data, layout } = spec;
  return (
    <div className="w-full mt-2" style={{ minHeight: 320 }}>
      <Plot
        data={data}
        layout={{ ...layout, responsive: true }}
        style={{ width: "100%", minHeight: 320 }}
        config={{ displayModeBar: false }}
      />
    </div>
  );
}

// ── FollowUps ──────────────────────────────────────────────────────────────

function FollowUps({ followUps, onSelect }) {
  if (!followUps?.length) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {followUps.map((q, i) => (
        <button
          key={i}
          onClick={() => onSelect(q)}
          className="text-xs bg-blue-50 border border-blue-200 text-blue-700 rounded-full
            px-3 py-1 hover:bg-blue-100 transition-colors"
        >
          {q}
        </button>
      ))}
    </div>
  );
}

// ── Message ────────────────────────────────────────────────────────────────

function Message({ msg, onFollowUp, sessionId }) {
  const isUser = msg.role === "user";
  const [pinned, setPinned] = useState(false);

  const pinToBoard = async () => {
    const type = msg.chartSpec ? "chart" : "text";
    const chartSpecStr = msg.chartSpec ? JSON.stringify(msg.chartSpec) : null;
    try {
      await fetch(`${API}/dashboard/${sessionId}/panels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          title: (msg.goal || msg.content || "").substring(0, 60),
          query_text: msg.goal || msg.content || "",
          answer: msg.content || "",
          chart_spec: chartSpecStr,
          panel_type: type,
        }),
      });
      setPinned(true);
      setTimeout(() => setPinned(false), 2000);
    } catch {}
  };

  const renderAnswer = () => {
    const text = msg.content ?? "";

    // Scalar: single number → large display
    if (isScalar(text)) {
      return (
        <div className="text-center py-2">
          <span style={{ fontSize: "3rem", fontWeight: "bold", lineHeight: 1 }}>{text.trim()}</span>
          <p className="text-xs text-gray-400 mt-1">result</p>
        </div>
      );
    }

    // Markdown table → DataTable component
    const tableData = parseMarkdownTable(text);
    if (tableData) {
      return <DataTable headers={tableData.headers} rows={tableData.rows} />;
    }

    // Markdown text (default)
    return (
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      </div>
    );
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm
          ${isUser
            ? "bg-blue-600 text-white"
            : "bg-white border border-gray-200 text-gray-800 shadow-sm"}`}
      >
        {isUser ? (
          <p>{msg.content}</p>
        ) : (
          <>
            {msg.content && renderAnswer()}
            {msg.chartSpec && <PlotlyChart spec={msg.chartSpec} />}
            {msg.followUps?.length > 0 && (
              <FollowUps followUps={msg.followUps} onSelect={onFollowUp} />
            )}
            <div className="mt-2 flex gap-3 text-xs text-gray-400 items-center flex-wrap">
              {msg.runId && (
                <a href="http://localhost:8001/traces" target="_blank" rel="noreferrer"
                  className="underline hover:text-blue-500">trace</a>
              )}
              {msg.cost != null && (
                <span>${msg.cost.toFixed(5)} · {(msg.inputTokens || 0) + (msg.outputTokens || 0)} tok</span>
              )}
              {!msg.content?.startsWith("Error:") && sessionId && (
                <button
                  onClick={pinToBoard}
                  className="ml-auto text-gray-400 hover:text-blue-600 transition-colors"
                  title="Pin to dashboard"
                >
                  {pinned ? "Pinned!" : "Pin to dashboard"}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── UploadPanel ────────────────────────────────────────────────────────────

function UploadPanel({ onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setUploading(true);
    setProgress("Uploading…");
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("name", file.name.replace(/\.[^.]+$/, ""));
    try {
      const res = await fetch(`${API}/datasets/upload`, { method: "POST", body: form });
      const body = await res.json();
      if (!body.ok) throw new Error(body.error || "Upload failed");
      setProgress("Done!");
      onUploaded(body.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
      setTimeout(() => setProgress(null), 1500);
    }
  }, [onUploaded]);

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
        ${dragging ? "border-blue-400 bg-blue-50" : "border-gray-300 hover:border-blue-300"}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.json"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {uploading ? (
        <p className="text-blue-600 font-medium">{progress || "Uploading…"}</p>
      ) : (
        <>
          <p className="text-gray-500 text-sm">
            Drop a <strong>CSV</strong> or <strong>JSON</strong> file here, or click to browse
          </p>
          {error && <p className="text-red-500 text-xs mt-2">{error}</p>}
          {progress === "Done!" && <p className="text-green-600 text-xs mt-2">Upload complete</p>}
        </>
      )}
    </div>
  );
}

// ── DatasetPanel ───────────────────────────────────────────────────────────

function DatasetPanel({ datasets, activeDataset, onUploaded, onSelect, onDelete }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Upload Dataset</h2>
        <UploadPanel onUploaded={onUploaded} />
      </div>

      {datasets.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Datasets</h2>
          <div className="flex flex-col gap-2">
            {datasets.map((ds) => {
              const cols = Object.keys(ds.schema?.columns || {}).length;
              const isActive = activeDataset?.dataset_id === ds.dataset_id;
              return (
                <div
                  key={ds.dataset_id}
                  className={`text-left text-xs rounded-lg px-3 py-2 border transition-colors
                    ${isActive
                      ? "bg-blue-100 border-blue-300 text-blue-800"
                      : "border-gray-200 hover:border-blue-200 text-gray-600"}`}
                >
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => onSelect(ds)}
                      className="font-medium text-left flex-1"
                    >
                      {ds.name}
                    </button>
                    <button
                      onClick={() => onDelete(ds.dataset_id)}
                      className="ml-2 text-gray-400 hover:text-red-500 transition-colors"
                      title="Delete dataset"
                    >
                      ✕
                    </button>
                  </div>
                  <p className="text-gray-400 mt-0.5">{ds.row_count} rows · {cols} cols</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-auto pt-4 border-t">
        <a
          href="http://localhost:8001/traces"
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-500 underline"
        >
          View all traces →
        </a>
      </div>
    </div>
  );
}

// ── SessionSidebar ─────────────────────────────────────────────────────────

function SessionSidebar({ open, onToggle, onLoadSession, onNewSession, currentSessionId }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedSession, setSelectedSession] = useState(null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/sessions`);
      const body = await res.json();
      if (body.ok) setSessions(body.data?.slice(0, 10) || []);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (open) fetchSessions();
  }, [open, fetchSessions]);

  const loadSession = useCallback(async (session) => {
    setSelectedSession(session);
    try {
      const res = await fetch(`${API}/sessions/${session.session_id || session.id}`);
      const body = await res.json();
      if (body.ok) onLoadSession(body.data);
    } catch {}
  }, [onLoadSession]);

  if (!open) {
    return (
      <button
        onClick={onToggle}
        className="fixed left-0 top-1/2 -translate-y-1/2 bg-white border border-gray-200
          rounded-r-lg px-2 py-3 text-xs text-gray-500 hover:text-blue-600 shadow-sm z-10
          writing-mode-vertical"
        title="Open session history"
      >
        ▶ History
      </button>
    );
  }

  return (
    <div className="w-64 shrink-0 bg-white border-r border-gray-200 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b bg-gray-50">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
          Session History
        </span>
        <button onClick={onToggle} className="text-gray-400 hover:text-gray-700 text-sm">
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <button
          onClick={() => { onNewSession(); }}
          className="w-full mb-3 text-xs bg-blue-600 text-white rounded-lg px-3 py-2
            hover:bg-blue-700 transition-colors"
        >
          + New Session
        </button>
        {loading && <p className="text-xs text-gray-400 text-center py-4">Loading…</p>}
        {!loading && sessions.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4">No sessions yet</p>
        )}
        <div className="flex flex-col gap-2">
          {sessions.map((s) => {
            const title = (s.first_query || s.title || "(untitled)").slice(0, 40);
            const inTok = s.total_input_tokens ?? 0;
            const outTok = s.total_output_tokens ?? 0;
            const isCurrent = s.session_id === currentSessionId || s.id === currentSessionId;
            return (
              <button
                key={s.session_id || s.id}
                onClick={() => loadSession(s)}
                className={`text-left rounded-lg px-3 py-2 border transition-colors text-xs
                  ${isCurrent
                    ? "bg-blue-50 border-blue-300"
                    : selectedSession?.session_id === s.session_id
                      ? "bg-gray-100 border-gray-300"
                      : "border-gray-200 hover:border-blue-200"}`}
              >
                <p className="font-medium text-gray-700 truncate">{title}</p>
                <p className="text-gray-400 mt-0.5">
                  {inTok}in / {outTok}out · {formatDate(s.created_at)}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── SessionHeader ──────────────────────────────────────────────────────────

function SessionHeader({ dataset, threadCost, threadTokens, onNewSession }) {
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b bg-white text-xs text-gray-500">
      <div className="flex gap-4 items-center">
        <span className="font-semibold text-gray-700">
          {dataset ? `Dataset: ${dataset.name}` : "No dataset"}
        </span>
        {threadTokens > 0 && (
          <span>{threadTokens.toLocaleString()} tok · ${threadCost.toFixed(5)}</span>
        )}
      </div>
      <div className="flex gap-3 items-center">
        <a
          href="/dashboard"
          className="text-blue-500 hover:text-blue-700 underline"
        >
          Dashboard
        </a>
        <button
          onClick={onNewSession}
          className="text-gray-400 hover:text-red-500 underline"
        >
          New session
        </button>
      </div>
    </div>
  );
}

// ── ChatPanel ──────────────────────────────────────────────────────────────

function ChatPanel({ sessionId, dataset, onTokenUpdate }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addUserMessage = useCallback((text) => {
    setMessages((prev) => [...prev, { id: genId(), role: "user", content: text }]);
  }, []);

  const send = useCallback(async (goal) => {
    const text = (goal ?? input).trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    addUserMessage(text);

    try {
      const reqBody = { goal: text, thread_id: sessionId };
      if (dataset?.dataset_id) reqBody.dataset_id = dataset.dataset_id;

      const res = await fetch(`${API}/runs`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(reqBody),
      });
      const json = await res.json();
      if (!json.ok) throw new Error(json.error || "Request failed");
      const d = json.data;

      let chartSpec = null;
      if (d.chart_spec) {
        try { chartSpec = typeof d.chart_spec === "string" ? JSON.parse(d.chart_spec) : d.chart_spec; }
        catch {}
      }

      setMessages((prev) => [...prev, {
        id: genId(),
        role: "assistant",
        content: d.answer || null,
        chartSpec,
        followUps: d.follow_ups || [],
        runId: d.run_id,
        cost: d.cost_usd,
        inputTokens: d.input_tokens,
        outputTokens: d.output_tokens,
      }]);
      onTokenUpdate?.(d.input_tokens || 0, d.output_tokens || 0, d.cost_usd || 0);
    } catch (e) {
      setMessages((prev) => [...prev, { id: genId(), role: "assistant", content: `Error: ${e.message}` }]);
    } finally {
      setSending(false);
    }
  }, [input, sending, sessionId, dataset, addUserMessage, onTokenUpdate]);

  const handleFollowUp = useCallback((q) => {
    send(q);
  }, [send]);

  return (
    <div className="flex flex-col flex-1 min-w-0 min-h-0">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-400 text-sm text-center">
            <div>
              <p className="text-2xl mb-2">📊</p>
              <p>Upload a CSV or JSON file, then ask questions in natural language.</p>
              <p className="mt-1 text-xs">You can also request charts: "show revenue by region as a bar chart"</p>
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <Message key={msg.id} msg={msg} onFollowUp={handleFollowUp} sessionId={sessionId} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t bg-white px-4 py-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder={dataset ? `Ask about ${dataset.name}…` : "Upload a dataset first, then ask questions"}
          disabled={sending}
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm
            focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-50"
          aria-label="goal"
        />
        <button
          onClick={() => send()}
          disabled={sending || !input.trim()}
          className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium
            hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          aria-label="Send"
        >
          {sending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────

export default function Page() {
  // [C-SSR-BROWSER-API]: all localStorage/sessionStorage reads inside useEffect only
  const [sessionId, setSessionId] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [threadCost, setThreadCost] = useState(0);
  const [threadTokens, setThreadTokens] = useState(0);
  const [stubMode, setStubMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pastQueries, setPastQueries] = useState([]);

  // [C-SESSION-SCOPE]: session ID generated in useEffect, never in state initialiser
  useEffect(() => {
    const sid = getOrCreate("analyst_session_id", genId);
    setSessionId(sid);

    // Load saved dataset
    const did = ls.get("dataset_id");
    if (did) {
      fetch(`${API}/datasets`).then((r) => r.json()).then((body) => {
        if (!body.ok) return;
        const list = body.data || [];
        setDatasets(list);
        const found = list.find((d) => d.dataset_id === did);
        if (found) setDataset(found);
      }).catch(() => {});
    } else {
      fetch(`${API}/datasets`).then((r) => r.json()).then((body) => {
        if (body.ok) setDatasets(body.data || []);
      }).catch(() => {});
    }

    // Restore thread tokens
    if (sid) {
      fetch(`${API}/threads/${sid}`).then((r) => r.json()).then((body) => {
        if (body.ok) {
          setThreadTokens(body.data.total_tokens || 0);
          setThreadCost(body.data.total_cost_usd || 0);
        }
      }).catch(() => {});
    }

    // Check stub mode
    fetch(`${API}/health`).then((r) => r.json()).then((body) => {
      if (body.stub_mode === true) setStubMode(true);
    }).catch(() => {});
  }, []);

  const handleUploaded = useCallback((ds) => {
    setDataset(ds);
    ls.set("dataset_id", ds.dataset_id);
    setDatasets((prev) => [ds, ...prev.filter((d) => d.dataset_id !== ds.dataset_id)]);
  }, []);

  const handleSelectDataset = useCallback((ds) => {
    setDataset(ds);
    ls.set("dataset_id", ds.dataset_id);
  }, []);

  const handleDeleteDataset = useCallback(async (datasetId) => {
    try {
      await fetch(`${API}/datasets/${datasetId}`, { method: "DELETE" });
    } catch {}
    setDatasets((prev) => prev.filter((d) => d.dataset_id !== datasetId));
    if (dataset?.dataset_id === datasetId) {
      setDataset(null);
      ls.remove("dataset_id");
    }
    // Refresh list
    fetch(`${API}/datasets`).then((r) => r.json()).then((body) => {
      if (body.ok) setDatasets(body.data || []);
    }).catch(() => {});
  }, [dataset]);

  const handleTokenUpdate = useCallback((inp, out, cost) => {
    setThreadTokens((t) => t + inp + out);
    setThreadCost((c) => c + cost);
  }, []);

  const newSession = useCallback(() => {
    const sid = genId();
    ls.set("analyst_session_id", sid);
    ls.remove("dataset_id");
    setSessionId(sid);
    setDataset(null);
    setThreadCost(0);
    setThreadTokens(0);
    setPastQueries([]);
  }, []);

  const handleLoadSession = useCallback((sessionData) => {
    // Show past queries in a history list (non-interactive)
    const queries = sessionData.runs?.map((r) => r.goal || r.query) || [];
    setPastQueries(queries);
  }, []);

  return (
    <div className="flex flex-col h-screen">
      {/* [C-STUB-BANNER]: visible banner when stub mode is active */}
      <StubBanner stubMode={stubMode} />

      <div className="flex flex-1 min-h-0 max-w-7xl mx-auto w-full">
        {/* Session Sidebar */}
        <SessionSidebar
          open={sidebarOpen}
          onToggle={() => setSidebarOpen((o) => !o)}
          onLoadSession={handleLoadSession}
          onNewSession={newSession}
          currentSessionId={sessionId}
        />

        {/* Main layout */}
        <div className="flex flex-col flex-1 min-w-0">
          <SessionHeader
            dataset={dataset}
            threadCost={threadCost}
            threadTokens={threadTokens}
            onNewSession={newSession}
          />

          <div className="flex flex-1 min-h-0">
            {/* Dataset Sidebar */}
            <div className="w-72 shrink-0 border-r bg-white p-4 overflow-y-auto">
              <DatasetPanel
                datasets={datasets}
                activeDataset={dataset}
                onUploaded={handleUploaded}
                onSelect={handleSelectDataset}
                onDelete={handleDeleteDataset}
              />
            </div>

            {/* Chat + Past Queries */}
            <div className="flex flex-col flex-1 min-w-0 min-h-0">
              {pastQueries.length > 0 && (
                <div className="border-b bg-yellow-50 px-4 py-2">
                  <p className="text-xs font-semibold text-gray-500 mb-1">Past queries (loaded session)</p>
                  <div className="flex flex-wrap gap-2">
                    {pastQueries.map((q, i) => (
                      <span key={i} className="text-xs bg-white border border-gray-200 rounded px-2 py-0.5 text-gray-600">
                        {q}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <ChatPanel
                key={sessionId}
                sessionId={sessionId}
                dataset={dataset}
                onTokenUpdate={handleTokenUpdate}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
