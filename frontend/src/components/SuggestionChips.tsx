/**
 * Phase-1/2 presentation per spec/ui.md: a single muted, clearly-labelled chip
 * standing in for the refinement suggestions that land in Phase 3.
 */
export default function SuggestionChips() {
  return (
    <div
      data-testid="suggestion-stub-chip"
      className="inline-flex items-center gap-2 rounded-full border border-dashed border-slate-300 bg-slate-50 px-3.5 py-1.5 text-sm font-medium text-slate-500"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M12 3v3M5.6 5.6l2.1 2.1M3 12h3M18 12h3M16.3 7.7l2.1-2.1M9 18h6M10 21h4M8.5 14.5a5 5 0 1 1 7 0c-.8.8-1.5 1.5-1.5 2.5h-4c0-1-.7-1.7-1.5-2.5Z" strokeLinecap="round" />
      </svg>
      Refinement suggestions — coming in Phase 3
    </div>
  )
}
