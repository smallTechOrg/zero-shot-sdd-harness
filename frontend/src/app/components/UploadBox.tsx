'use client'

import { useRef, useState } from 'react'
import { uploadDataset, ApiError } from '../lib/api'
import type { Dataset } from '../lib/types'

const ACCEPT = '.csv,.xlsx'

export default function UploadBox({ onLoaded }: { onLoaded: (d: Dataset) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  async function handleFile(file: File | undefined) {
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      const dataset = await uploadDataset(file)
      onLoaded(dataset)
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError('Network error — is the server running?')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="w-full">
      <div
        role="button"
        tabIndex={0}
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={e => {
          if ((e.key === 'Enter' || e.key === ' ') && !uploading) inputRef.current?.click()
        }}
        onDragOver={e => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => {
          e.preventDefault()
          setDragging(false)
          if (!uploading) handleFile(e.dataTransfer.files?.[0])
        }}
        data-testid="upload-box"
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-12 text-center transition-colors ${
          dragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 bg-white hover:border-blue-400 hover:bg-gray-50'
        } ${uploading ? 'pointer-events-none opacity-70' : ''}`}
      >
        {uploading ? (
          <>
            <Spinner />
            <p className="text-sm font-medium text-gray-700">Uploading &amp; profiling…</p>
          </>
        ) : (
          <>
            <div className="text-4xl" aria-hidden>
              ⬆
            </div>
            <p className="text-base font-semibold text-gray-800">
              Drop a spreadsheet here, or click to browse
            </p>
            <p className="text-sm text-gray-500">Accepts .csv or .xlsx files</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          data-testid="file-input"
          onChange={e => handleFile(e.target.files?.[0])}
        />
      </div>

      {error && (
        <div
          role="alert"
          data-testid="upload-error"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {error}
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <div
      className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600"
      aria-label="loading"
    />
  )
}
