'use client'

import { useRef, useState } from 'react'
import { uploadDataset, type Dataset } from '@/lib/api'

interface Props {
  onUploaded: (dataset: Dataset) => void
}

export default function UploadZone({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(file: File | undefined) {
    if (!file) return
    setError(null)
    setLoading(true)
    try {
      const dataset = await uploadDataset(file)
      onUploaded(dataset)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div data-testid="upload-zone">
      <div
        onDragOver={e => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => {
          e.preventDefault()
          setDragging(false)
          if (!loading) handleFile(e.dataTransfer.files?.[0])
        }}
        onClick={() => !loading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload a CSV or Excel file"
        className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition ${
          dragging
            ? 'border-indigo-500 bg-indigo-50'
            : 'border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50'
        } ${loading ? 'pointer-events-none opacity-70' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls,text/csv"
          className="hidden"
          onChange={e => handleFile(e.target.files?.[0])}
          data-testid="file-input"
        />
        {loading ? (
          <>
            <Spinner />
            <p className="mt-3 text-sm font-medium text-slate-700">Uploading & profiling…</p>
            <p className="mt-1 text-xs text-slate-400">Loading the full dataset server-side</p>
          </>
        ) : (
          <>
            <svg
              className="h-10 w-10 text-indigo-400"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="mt-3 text-base font-semibold text-slate-800">
              Drop a CSV or Excel file here
            </p>
            <p className="mt-1 text-sm text-slate-500">or click to browse · up to ~100MB</p>
          </>
        )}
      </div>

      {error && (
        <div
          data-testid="upload-error"
          className="mt-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          <span className="font-semibold">Upload failed:</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <svg className="h-8 w-8 animate-spin text-indigo-500" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
      />
    </svg>
  )
}
