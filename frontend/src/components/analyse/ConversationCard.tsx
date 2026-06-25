'use client'

import { StubPill, StubNote } from '@/components/StubBanner'

/**
 * Conversation card (C2, C3, C6, C7, C22, C23, C32) — Phase-1 labelled stub.
 *
 * Renders the empty thread (role="log", aria-live="polite"), a disabled
 * question textarea, and a disabled Ask button. No /ask call is made; the
 * conversation becomes real in Phase 2.
 */
export function ConversationCard() {
  return (
    <section
      aria-labelledby="conversation-heading"
      className="flex min-h-[20rem] flex-col rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="conversation-heading" className="text-sm font-semibold text-gray-800">
          Conversation
        </h2>
        <StubPill phase={2} />
      </div>

      {/* Thread — empty in Phase 1, but the a11y hooks from ui.md are present. */}
      <div
        role="log"
        aria-live="polite"
        aria-label="Conversation thread"
        className="flex flex-1 items-center justify-center rounded-md border border-dashed border-gray-200 bg-gray-50 px-4 py-10 text-center"
      >
        <p className="text-xs text-gray-400">
          Your questions and the agent&apos;s answers will appear here.
          <StubNote>
            Ask / answer, the steps inspector, token counts, and follow-up
            suggestions arrive in Phase 2.
          </StubNote>
        </p>
      </div>

      {/* Composer — disabled placeholder. */}
      <div className="mt-3">
        <label htmlFor="question-input" className="sr-only">
          Ask a question (coming in Phase 2)
        </label>
        <textarea
          id="question-input"
          rows={3}
          disabled
          aria-disabled="true"
          placeholder="Ask a question about your data… (coming in Phase 2)"
          className="w-full cursor-not-allowed resize-none rounded-md border border-gray-200 bg-gray-50 p-3 text-sm text-gray-400 placeholder:text-gray-400"
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-xs text-gray-400">Enter to send · Shift+Enter for a new line</span>
          <button
            type="button"
            disabled
            aria-disabled="true"
            title="Coming in Phase 2"
            className="cursor-not-allowed rounded-md bg-gray-200 px-5 py-2 text-sm font-medium text-gray-400"
          >
            Ask
          </button>
        </div>
      </div>
    </section>
  )
}
