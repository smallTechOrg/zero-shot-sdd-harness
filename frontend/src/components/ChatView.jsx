import React, { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useChat } from '../hooks/useChat.js'
import MessageThread from './MessageThread.jsx'
import TokenBudgetBar from './TokenBudgetBar.jsx'
import UploadModal from './UploadModal.jsx'

export default function ChatView() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { session, messages, datasets, loading, queryLoading, error, tokenUsage, sendQuery, uploadFile } = useChat(sessionId)
  const [input, setInput] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!queryLoading && inputRef.current) {
      inputRef.current.focus()
    }
  }, [queryLoading])

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || queryLoading) return
    setInput('')
    sendQuery(q)
  }

  if (loading) {
    return <div className="p-8 text-gray-500">Loading session...</div>
  }

  return (
    <div className="flex h-screen">
      {/* Left panel: datasets */}
      <div className="w-64 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <button onClick={() => navigate('/')} className="text-sm text-blue-600 hover:underline">
            &larr; All Sessions
          </button>
          <h2 className="font-semibold text-gray-900 mt-2">{session?.title || 'Session'}</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Datasets</span>
            <button
              onClick={() => setShowUpload(true)}
              className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
            >
              + Upload
            </button>
          </div>
          {datasets.length === 0 ? (
            <p className="text-xs text-gray-400">No datasets yet. Upload a file to start.</p>
          ) : (
            <ul className="space-y-2">
              {datasets.map(ds => (
                <li key={ds.dataset_id} className="text-sm">
                  <div className="font-medium text-gray-800">{ds.original_filename}</div>
                  <div className="text-xs text-gray-500">{ds.row_count.toLocaleString()} rows &middot; {ds.table_name}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Right panel: chat */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}
          {messages.length === 0 ? (
            <div className="text-center text-gray-400 mt-12">
              <p className="text-lg">Ask a question about your data</p>
              <p className="text-sm mt-1">Upload a CSV, JSON, or Parquet file to get started</p>
            </div>
          ) : (
            <MessageThread messages={messages} />
          )}
          {queryLoading && (
            <div className="flex items-center gap-2 text-gray-400 mt-4">
              <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-blue-600 rounded-full" />
              <span className="text-sm">Thinking...</span>
            </div>
          )}
        </div>

        {tokenUsage && <TokenBudgetBar tokenUsage={tokenUsage} hardCap={32000} />}

        <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4 bg-white">
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={queryLoading}
              placeholder={datasets.length === 0 ? 'Upload a dataset first...' : 'Ask a question about your data...'}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <button
              type="submit"
              disabled={queryLoading || !input.trim()}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              Ask
            </button>
          </div>
        </form>
      </div>

      {showUpload && (
        <UploadModal
          onUpload={uploadFile}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  )
}
