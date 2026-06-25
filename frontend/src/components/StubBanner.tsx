'use client'

/**
 * Phase-1 stub primitives.
 *
 * Everything in the Data Analysis Agent shell is a clearly-labelled,
 * NON-FUNCTIONAL placeholder in Phase 1. These two components make that
 * unambiguous so a stub is never mistaken for a bug:
 *
 *  - <StubBanner />  : the persistent yellow "stub mode" banner from spec/ui.md.
 *  - <StubPill />    : a small "Phase N — not yet wired" tag reused on every
 *                      placeholder control across both tabs.
 */

export function StubBanner() {
  return (
    <div
      role="status"
      className="border-b border-yellow-300 bg-yellow-100 px-4 py-2 text-center text-sm text-yellow-900"
    >
      <span className="font-semibold">Stub mode</span> — this is a preview shell.
      Every control below is a labelled, non-functional placeholder. Real
      uploads, questions, and answers arrive in later phases.
    </div>
  )
}

export function StubPill({ phase = 2, label }: { phase?: number; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-yellow-300 bg-yellow-50 px-2 py-0.5 text-[11px] font-medium whitespace-nowrap text-yellow-800">
      <span aria-hidden="true">●</span>
      {label ?? `Phase ${phase} — not yet wired`}
    </span>
  )
}

/**
 * A standardised "coming in a later phase" note. Use under a placeholder
 * control to spell out, in plain words, that it does nothing yet.
 */
export function StubNote({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-xs text-gray-400">{children}</p>
}
