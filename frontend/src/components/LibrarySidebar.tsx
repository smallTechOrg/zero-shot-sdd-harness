import StubCard from './StubCard'

export default function LibrarySidebar() {
  return (
    <aside className="space-y-3" data-testid="library-sidebar">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
        Library &amp; History
      </h2>
      <StubCard
        title="File library"
        phase="Phase 4"
        description="Your saved files, persisted across sessions. List, select, and delete."
      />
      <StubCard
        title="Question history"
        phase="Phase 4"
        description="Revisit past answers with their plan, code, and results intact."
      />
      <StubCard
        title="Conversation thread"
        phase="Phase 4"
        description="Durable chat that carries context within and across days."
      />
    </aside>
  )
}
