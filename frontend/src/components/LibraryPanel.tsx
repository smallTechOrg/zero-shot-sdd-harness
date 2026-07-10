import StubPanel from './StubPanel'

export default function LibraryPanel() {
  return (
    <StubPanel
      testId="stub-library"
      title="Library"
      phase={3}
      description="This panel will show the browsable audit trail — every design run with verdict, cost and duration, one-click run replay, and the presets editor."
      icon={
        <svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M4 4.5h5l2 2.5h9v12.5H4V4.5Z" />
          <path d="M4 9.5h16" />
        </svg>
      }
    />
  )
}
