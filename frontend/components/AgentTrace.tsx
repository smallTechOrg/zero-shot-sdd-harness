"use client";

import { useState } from "react";

import type { TraceStep } from "@/lib/api";

export default function AgentTrace({ steps, live }: { steps: TraceStep[]; live?: boolean }) {
  const [open, setOpen] = useState(Boolean(live));
  if (!steps.length) return null;
  return (
    <div className="mt-2 text-xs" data-testid="agent-trace">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-slate-500 underline-offset-2 hover:underline"
      >
        {open ? "▾" : "▸"} {live ? "Working…" : `Agent trace (${steps.length} steps)`}
      </button>
      {open ? (
        <ol className="mt-1 space-y-1 border-l-2 border-slate-200 pl-3">
          {steps.map((s, i) => (
            <li key={i} className={s.is_error ? "text-rose-600" : "text-slate-600"}>
              {s.description}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
