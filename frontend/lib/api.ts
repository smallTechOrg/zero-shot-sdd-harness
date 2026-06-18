// API client for the DataChat backend (HTTP + SSE). Base URL is configurable.

// Default to same-origin (empty base → relative URLs) since FastAPI serves this UI at :8001.
// Override with NEXT_PUBLIC_API_BASE to point at a separately-hosted API (e.g. dev on :3000).
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export type ColumnSchema = { name: string; type: string };
export type FileRead = {
  id: string;
  filename: string;
  row_count: number;
  schema_columns: ColumnSchema[];
};
export type Dataset = {
  id: string;
  name: string;
  created_at: string;
  files: FileRead[];
};
export type ResultTable = { columns: string[]; rows: unknown[][] };
export type ChartSpec = {
  type: "bar" | "line" | "pie";
  title: string;
  x: string;
  y: string;
  data: { x: unknown; y: unknown }[];
};
export type TraceStep = {
  description: string;
  action: string;
  result: string;
  is_error: boolean;
};
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  result_table: ResultTable | null;
  chart: ChartSpec | null;
  trace: TraceStep[] | null;
  created_at: string;
};

type Envelope<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string } };

async function unwrap<T>(res: Response): Promise<T> {
  const body = (await res.json()) as Envelope<T>;
  if (!body.ok) throw new Error(body.error.message || "Request failed");
  return body.data;
}

export async function listDatasets(): Promise<Dataset[]> {
  return unwrap<Dataset[]>(await fetch(`${API_BASE}/datasets`, { cache: "no-store" }));
}

export async function createDataset(name: string): Promise<Dataset> {
  return unwrap<Dataset>(
    await fetch(`${API_BASE}/datasets`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
}

export async function uploadFiles(datasetId: string, files: File[]): Promise<{ files: FileRead[] }> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return unwrap<{ files: FileRead[] }>(
    await fetch(`${API_BASE}/datasets/${datasetId}/files`, { method: "POST", body: form }),
  );
}

export async function createConversation(datasetId: string): Promise<{ id: string }> {
  return unwrap<{ id: string }>(
    await fetch(`${API_BASE}/conversations`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dataset_id: datasetId }),
    }),
  );
}

export async function getConversation(id: string): Promise<{ messages: Message[] }> {
  return unwrap<{ messages: Message[] }>(
    await fetch(`${API_BASE}/conversations/${id}`, { cache: "no-store" }),
  );
}

export type StreamEvent =
  | { event: "step"; data: TraceStep }
  | { event: "answer"; data: Message }
  | { event: "done"; data: Record<string, unknown> }
  | { event: "error"; data: { code: string; message: string } };

function parseSseChunk(chunk: string): StreamEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) } as StreamEvent;
  } catch {
    return null;
  }
}

// Stream a question's SSE response, invoking onEvent for each event. EventSource only
// supports GET, so we read the POST body's text/event-stream from the fetch ReadableStream.
// A plain callback loop (not an async generator) avoids the response being released while
// the consumer suspends on React state updates between events.
export async function streamQuery(
  conversationId: string,
  question: string,
  onEvent: (ev: StreamEvent) => void,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/conversations/${conversationId}/query`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch (e) {
    onEvent({ event: "error", data: { code: "NETWORK", message: (e as Error).message } });
    return;
  }

  if (!res.ok || !res.body) {
    let msg = `Request failed (${res.status})`;
    try {
      const b = await res.json();
      msg = b?.error?.message || msg;
    } catch {
      /* non-JSON */
    }
    onEvent({ event: "error", data: { code: "HTTP_ERROR", message: msg } });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (value) {
      // sse-starlette uses CRLF line endings; normalize so we can split on a blank line.
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() ?? "";
      for (const chunk of chunks) {
        const ev = parseSseChunk(chunk);
        if (ev) onEvent(ev);
      }
    }
    if (done) break;
  }
  const tail = parseSseChunk(buffer);
  if (tail) onEvent(tail);
}
