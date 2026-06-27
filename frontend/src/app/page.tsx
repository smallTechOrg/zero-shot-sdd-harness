'use client'

import { useState } from 'react'
import Sidebar from '@/components/Sidebar'
import UploadPanel from '@/components/UploadPanel'
import AnalysisPanel from '@/components/AnalysisPanel'
import ResultsPanel from '@/components/ResultsPanel'
import { UploadResult, AnalysisResult } from '@/lib/api'

export default function Home() {
  const [activeUpload, setActiveUpload] = useState<UploadResult | null>(null)
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [sidebarRefresh, setSidebarRefresh] = useState(0)
  const [isRunning, setIsRunning] = useState(false)

  function handleUploadSuccess(result: UploadResult) {
    setActiveUpload(result)
    setAnalysisResult(null)
    // Trigger sidebar refresh to show new upload
    setSidebarRefresh((n) => n + 1)
  }

  function handleSelectUpload(upload: UploadResult) {
    setActiveUpload(upload)
    setAnalysisResult(null)
  }

  function handleAnalysisResult(result: AnalysisResult) {
    setAnalysisResult(result)
  }

  function handleNewUpload() {
    setActiveUpload(null)
    setAnalysisResult(null)
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center justify-between px-6 py-4">
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">Data Analysis Agent</h1>
          {activeUpload && (
            <button
              onClick={handleNewUpload}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
            >
              + New Upload
            </button>
          )}
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1">
        {/* Sidebar */}
        <Sidebar
          activeUploadId={activeUpload?.upload_id ?? null}
          onSelectUpload={handleSelectUpload}
          onNewUpload={handleNewUpload}
          refreshTrigger={sidebarRefresh}
        />

        {/* Main panel */}
        <main className="flex-1 p-8 overflow-y-auto bg-gray-50">
          {!activeUpload ? (
            /* Upload panel — shown when no file is selected */
            <UploadPanel onUploadSuccess={handleUploadSuccess} />
          ) : (
            /* Analysis + results panels — shown after upload/selection */
            <div className="max-w-4xl mx-auto space-y-6">
              <AnalysisPanel
                activeUpload={activeUpload}
                onAnalysisResult={handleAnalysisResult}
                onRunningChange={setIsRunning}
              />
              <ResultsPanel
                result={analysisResult}
                isLoading={isRunning}
                onRetry={() => setAnalysisResult(null)}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
