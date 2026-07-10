import StubPanel from './StubPanel'

export default function Model3DViewer() {
  return (
    <StubPanel
      testId="stub-3d-model"
      title="3D Model"
      phase={3}
      description="This panel will show an interactive 3D model of the culvert (orbit/zoom in the browser) built from the same parameters, with a STEP download that opens in FreeCAD."
      icon={
        <svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 2.5 21 7v10l-9 4.5L3 17V7l9-4.5Z" />
          <path d="M12 11.5 21 7M12 11.5 3 7M12 11.5v10" />
        </svg>
      }
    />
  )
}
