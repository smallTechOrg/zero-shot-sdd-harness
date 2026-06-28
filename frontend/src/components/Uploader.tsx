'use client'

import { useRef, useState } from 'react'
import { StubBadge } from './StubPanel'

interface UploaderProps {
  onUpload: (file: File) => void
  loading: boolean
  error: string | null
  hasDataset: boolean
}

export function Uploader({ onUpload, loading, error, hasDataset }: UploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  function pickFile(files: FileList | null) {
    if (!files || files.length === 0) return
    onUpload(files[0])
  }

  return (
    <section data-testid="uploader" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">
          {hasDataset ? 'Upload another CSV' : 'Upload a CSV'}
        </h2>
        <div
          data-stub="true"
          aria-disabled="true"
          className="pointer-events-none flex items-center gap-2 text-xs text-gray-400"
        >
          <span>Excel (.xlsx)</span>
          <StubBadge phase="Phase 5" />
        </div>
      </div>

      <div
        role="button"
        tabIndex={0}
        onClick={() => !loading && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !loading) inputRef.current?.click()
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (!loading) pickFile(e.dataTransfer.files)
        }}
        className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:border-blue-400'
        } ${loading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          data-testid="file-input"
          onChange={(e) => pickFile(e.target.files)}
          disabled={loading}
        />
        {loading ? (
          <div data-testid="upload-loading" className="flex items-center gap-3 text-sm text-gray-600">
            <svg className="h-5 w-5 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span>Profiling your data…</span>
          </div>
        ) : (
          <>
            <svg className="mb-2 h-8 w-8 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5V18a2 2 0 002 2h14a2 2 0 002-2v-1.5M12 3v13m0-13l-4 4m4-4l4 4" />
            </svg>
            <p className="text-sm font-medium text-gray-700">Drag a .csv here, or click to choose</p>
            <p className="mt-1 text-xs text-gray-400">Up to ~100MB. CSV only for now.</p>
          </>
        )}
      </div>

      {error && (
        <div
          data-testid="upload-error"
          role="alert"
          className="mt-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm font-medium text-red-700"
        >
          {error}
        </div>
      )}
    </section>
  )
}
