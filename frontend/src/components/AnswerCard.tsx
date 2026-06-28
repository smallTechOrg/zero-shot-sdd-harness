'use client'

interface AnswerCardProps {
  answer: string
}

export default function AnswerCard({ answer }: AnswerCardProps) {
  return (
    <section
      aria-label="Answer"
      data-testid="answer-card"
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-400">Answer</h2>
      <p className="whitespace-pre-wrap text-base leading-relaxed text-gray-900">{answer}</p>
    </section>
  )
}

interface FailureCardProps {
  attempts: number
  error?: string
}

export function FailureCard({ attempts, error }: FailureCardProps) {
  return (
    <section
      role="alert"
      aria-label="Run failed"
      data-testid="failure-card"
      className="rounded-xl border border-red-200 bg-red-50 p-5 shadow-sm"
    >
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-red-500">Couldn&apos;t answer</h2>
      <p className="text-base leading-relaxed text-red-900">
        Couldn&apos;t answer this after {attempts} attempt{attempts === 1 ? '' : 's'} — see the errors above.
      </p>
      {error && <p className="mt-2 font-mono text-xs text-red-700">{error}</p>}
    </section>
  )
}
