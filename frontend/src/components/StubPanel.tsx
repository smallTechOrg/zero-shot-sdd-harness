import type { ReactNode } from 'react'

interface StubPanelProps {
  testId: string
  title: string
  phase: 2 | 3
  /** "This panel will …" — what appears when the phase lands. */
  description: string
  icon: ReactNode
}

/**
 * A labelled not-yet-built panel per spec/ui.md stub rules: dashed border,
 * muted icon, "Coming in Phase N" badge, and an unmistakable lead-in stating
 * BOTH the arrival phase AND that there is nothing to try yet. Never a
 * spinner, never red — a stub must never look like a bug.
 */
export default function StubPanel({ testId, title, phase, description, icon }: StubPanelProps) {
  return (
    <div
      data-testid={testId}
      className="flex h-full min-h-[24rem] flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-10 text-center"
    >
      <div className="text-slate-400" aria-hidden="true">
        {icon}
      </div>
      <span className="inline-flex items-center rounded-full bg-slate-200 px-4 py-1.5 text-base font-semibold text-slate-700">
        Coming in Phase {phase}
      </span>
      <h3 className="text-xl font-semibold text-slate-700">{title}</h3>
      <p className="max-w-md text-base leading-relaxed text-slate-600">
        <strong className="font-semibold text-slate-800">
          Coming in Phase {phase} — nothing to try here yet.
        </strong>{' '}
        {description}
      </p>
    </div>
  )
}
