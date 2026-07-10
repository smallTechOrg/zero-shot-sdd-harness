import StubPanel from './StubPanel'

export default function CalcSheet() {
  return (
    <StubPanel
      testId="stub-calc-sheet"
      title="Calc Sheet"
      phase={2}
      description="The clause-cited calculation sheet — EUDL + CDA loading, analysis and member checks with drill-down to every formula — lands in Phase 2."
      icon={
        <svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="4" y="2.5" width="16" height="19" rx="2" />
          <path d="M8 7h8M8 11h8M8 15h5" />
        </svg>
      }
    />
  )
}
