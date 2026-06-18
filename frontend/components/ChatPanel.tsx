"use client";

import { useEffect, useRef, useState } from "react";

import AgentTrace from "@/components/AgentTrace";
import MessageBubble from "@/components/MessageBubble";
import {
  createConversation,
  getConversation,
  streamQuery,
  type Dataset,
  type Message,
  type TraceStep,
} from "@/lib/api";

export default function ChatPanel({ dataset }: { dataset: Dataset }) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [liveSteps, setLiveSteps] = useState<TraceStep[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const hasFiles = dataset.files.length > 0;

  // Reset the conversation when the selected dataset changes.
  useEffect(() => {
    setConversationId(null);
    setMessages([]);
    setLiveSteps([]);
    setError(null);
  }, [dataset.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveSteps]);

  async function ensureConversation(): Promise<string> {
    if (conversationId) return conversationId;
    const conv = await createConversation(dataset.id);
    setConversationId(conv.id);
    return conv.id;
  }

  async function send() {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    setQuestion("");
    setLiveSteps([]);

    const userMsg: Message = {
      id: `local-${Date.now()}`,
      role: "user",
      content: q,
      result_table: null,
      chart: null,
      trace: null,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);

    try {
      const convId = await ensureConversation();
      await streamQuery(convId, q, (ev) => {
        if (ev.event === "step") {
          setLiveSteps((s) => [...s, ev.data]);
        } else if (ev.event === "answer") {
          setMessages((m) => [...m, ev.data]);
          setLiveSteps([]);
        } else if (ev.event === "error") {
          setError(ev.data.message);
          setLiveSteps([]);
        }
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // Allow loading prior history (e.g. on reconnect) — used after a conversation exists.
  async function reload() {
    if (!conversationId) return;
    const { messages: msgs } = await getConversation(conversationId);
    setMessages(msgs);
  }
  void reload;

  return (
    <section className="flex flex-1 flex-col" data-testid="chat-panel">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <h2 className="font-medium">{dataset.name}</h2>
        <p className="text-xs text-slate-500">
          {hasFiles
            ? "Ask a question about this dataset in plain English."
            : "Upload a CSV on the left to start asking questions."}
        </p>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4" data-testid="message-thread">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {busy && liveSteps.length > 0 ? (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-2xl bg-white px-4 py-2.5 shadow-sm ring-1 ring-slate-200">
              <AgentTrace steps={liveSteps} live />
            </div>
          </div>
        ) : null}
        {busy && liveSteps.length === 0 ? (
          <p className="text-sm text-slate-400" data-testid="thinking">
            Thinking…
          </p>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {error ? (
        <div className="px-6 pb-2 text-sm text-rose-600" data-testid="chat-error">
          {error}
        </div>
      ) : null}

      <div className="flex gap-2 border-t border-slate-200 bg-white px-6 py-4">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={!hasFiles || busy}
          placeholder={hasFiles ? "e.g. total sales by region as a bar chart" : "Upload a CSV first"}
          data-testid="question-input"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
        />
        <button
          onClick={send}
          disabled={!hasFiles || busy || !question.trim()}
          data-testid="send"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </section>
  );
}
