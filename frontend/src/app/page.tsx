'use client'

import { useState, useEffect, useCallback } from 'react'
import Sidebar from '../components/Sidebar'
import QueryPanel from '../components/QueryPanel'
import AuditTab from '../components/AuditTab'
import { getDatasets, uploadDataset } from '../lib/api'
import type { Dataset, QueryResult } from '../types'

const SESSION_KEY = 'analyst_session_id'

type ActiveView = 'query' | 'audit'

export default function Home() {
  const [sessionId, setSessionId] = useState<string>('')
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [activeView, setActiveView] = useState<ActiveView>('query')
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null)
  const [queryHistory, setQueryHistory] = useState<QueryResult[]>([])
  const [isQuerying, setIsQuerying] = useState(false)
  const [loadingDatasets, setLoadingDatasets] = useState(false)
  const [datasetsError, setDatasetsError] = useState<string | null>(null)

  // Initialise or restore session ID from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(SESSION_KEY)
    if (stored) {
      setSessionId(stored)
    } else {
      const newId = crypto.randomUUID()
      localStorage.setItem(SESSION_KEY, newId)
      setSessionId(newId)
    }
  }, [])

  // Load datasets when session ID is ready
  const loadDatasets = useCallback(async (sid: string) => {
    if (!sid) return
    setLoadingDatasets(true)
    setDatasetsError(null)
    try {
      const data = await getDatasets(sid)
      setDatasets(data)
    } catch (e: unknown) {
      setDatasetsError(e instanceof Error ? e.message : 'Failed to load datasets')
    } finally {
      setLoadingDatasets(false)
    }
  }, [])

  useEffect(() => {
    if (sessionId) {
      loadDatasets(sessionId)
    }
  }, [sessionId, loadDatasets])

  async function handleUpload(file: File) {
    // Throws on error — Sidebar handles the error display
    const dataset = await uploadDataset(sessionId, file)
    setDatasets((prev) => {
      // Avoid duplicates (same id)
      const exists = prev.find((d) => d.id === dataset.id)
      if (exists) return prev
      return [...prev, dataset]
    })
    // Auto-select newly uploaded dataset
    setSelectedDataset(dataset)
  }

  function handleQueryComplete(result: QueryResult) {
    setQueryHistory((prev) => [...prev, result])
  }

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* Left sidebar */}
      <Sidebar
        datasets={datasets}
        onUpload={handleUpload}
        selectedDataset={selectedDataset}
        onSelectDataset={setSelectedDataset}
        sessionId={sessionId}
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top nav bar */}
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveView('query')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                activeView === 'query'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Query
            </button>
            <button
              onClick={() => setActiveView('audit')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                activeView === 'audit'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Audit Log
            </button>
          </div>

          <div className="flex items-center gap-3">
            {/* Dataset loading state */}
            {loadingDatasets && (
              <span className="text-xs text-gray-400 flex items-center gap-1">
                <span className="w-3 h-3 border border-gray-300 border-t-blue-500 rounded-full animate-spin" />
                Loading datasets…
              </span>
            )}
            {datasetsError && (
              <span className="text-xs text-red-500" title={datasetsError}>
                Dataset load error
              </span>
            )}
            <span className="text-sm font-semibold text-gray-800">Senior Data Analyst</span>
          </div>
        </header>

        {/* Main view area */}
        <main className="flex-1 min-h-0 overflow-hidden bg-gray-50">
          {activeView === 'query' ? (
            <QueryPanel
              selectedDataset={selectedDataset}
              sessionId={sessionId}
              queryHistory={queryHistory}
              onQueryComplete={handleQueryComplete}
              isQuerying={isQuerying}
              setIsQuerying={setIsQuerying}
            />
          ) : (
            sessionId ? (
              <AuditTab sessionId={sessionId} />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                Initialising session…
              </div>
            )
          )}
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-gray-200 px-4 py-2 shrink-0">
          <p className="text-xs text-gray-400 text-center">
            Session ID:{' '}
            <span className="font-mono text-gray-500" title={sessionId}>
              {sessionId || 'Initialising…'}
            </span>
          </p>
        </footer>
      </div>
    </div>
  )
}
