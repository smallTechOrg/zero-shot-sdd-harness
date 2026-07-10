import StubPanel from './StubPanel'

export default function ProofCheckPanel() {
  return (
    <StubPanel
      testId="stub-proof-check"
      title="Proof-Check"
      phase={2}
      description="The automatic severity-graded proof-check memo, IRS CBC compliance matrix and BMD/SFD diagrams with an independent FE cross-check land in Phase 2."
      icon={
        <svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 2.5 20 6v6c0 5-3.5 8.5-8 9.5-4.5-1-8-4.5-8-9.5V6l8-3.5Z" />
          <path d="m8.5 12 2.5 2.5 4.5-5" />
        </svg>
      }
    />
  )
}
