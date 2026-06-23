'use client'

import { useRef, useState } from 'react'
import type { Dataset } from '../types'

interface Props {
  datasets: Dataset[]
  onUpload: (file: File) => Promise<void>
  selectedDataset: Dataset | null
  onSelectDataset: (dataset: Dataset) => void
  sessionId: string
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString()
  } catch {
    return iso
  }
}

function parseColumnNames(columnNames: string): string[] {
  try {
    return JSON.parse(columnNames)
  } catch {
    return []
  }
}

export default function Sidebar({
  datasets,
  onUpload,
  selectedDataset,
  onSelectDataset,
  sessionId,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError(null)
    setUploading(true)
    try {
      await onUpload(file)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setUploadError(msg)
      // Clear error after 5 seconds
      setTimeout(() => setUploadError(null), 5000)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <aside className="h-full flex flex-col bg-gray-900 text-white w-64 shrink-0">
      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-700">
        <h1 className="text-base font-bold tracking-tight">Data Analyst</h1>
        <p className="text-xs text-gray-400 mt-0.5">AI-powered data analysis</p>
      </div>

      {/* Upload section */}
      <div className="px-3 py-3 border-b border-gray-700">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={handleFileChange}
          disabled={uploading}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Uploading…
            </span>
          ) : (
            '+ Upload Dataset'
          )}
        </button>
        <p className="text-xs text-gray-500 mt-1.5 text-center">CSV, XLSX, XLS</p>

        {uploadError && (
          <div className="mt-2 rounded bg-red-900/50 border border-red-700 px-3 py-2 text-xs text-red-300">
            {uploadError}
          </div>
        )}
      </div>

      {/* Dataset list */}
      <div className="flex-1 overflow-y-auto">
        {datasets.length === 0 ? (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-gray-500">No datasets uploaded yet.</p>
            <p className="text-xs text-gray-600 mt-1">Upload a CSV or Excel file to get started.</p>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            <p className="text-xs text-gray-500 px-2 py-1 uppercase tracking-wider">
              Datasets ({datasets.length})
            </p>
            {datasets.map((ds) => {
              const cols = parseColumnNames(ds.column_names)
              const isSelected = selectedDataset?.id === ds.id
              return (
                <button
                  key={ds.id}
                  onClick={() => onSelectDataset(ds)}
                  className={`w-full text-left rounded-lg px-3 py-2.5 transition-colors ${
                    isSelected
                      ? 'bg-blue-700 text-white'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  }`}
                >
                  <p className="text-sm font-medium truncate" title={ds.original_filename}>
                    {ds.original_filename}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                        isSelected ? 'bg-blue-600 text-blue-100' : 'bg-gray-700 text-gray-300'
                      }`}
                    >
                      {ds.row_count.toLocaleString()} rows
                    </span>
                    {cols.length > 0 && (
                      <span className={`text-xs ${isSelected ? 'text-blue-200' : 'text-gray-500'}`}>
                        {cols.length} cols
                      </span>
                    )}
                  </div>
                  <p className={`text-xs mt-0.5 ${isSelected ? 'text-blue-200' : 'text-gray-600'}`}>
                    {formatDate(ds.created_at)}
                  </p>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Footer — session ID */}
      <div className="px-3 py-2 border-t border-gray-700 shrink-0">
        <p className="text-xs text-gray-600">Session</p>
        <p
          className="text-xs text-gray-500 font-mono truncate"
          title={sessionId}
        >
          {sessionId ? sessionId.slice(0, 18) + '…' : 'Loading…'}
        </p>
      </div>
    </aside>
  )
}
