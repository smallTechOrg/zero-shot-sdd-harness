'use client'

import { useRef, useState } from 'react'

interface Dataset {
  dataset_id: string
  filename: string
  row_count: number
  column_names: string[]
}

interface CsvUploadProps {
  onUploadSuccess: (dataset: Dataset) => void
  disabled?: boolean
}

export default function CsvUpload({ onUploadSuccess, disabled = false }: CsvUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFileSelect(file: File) {
    if (!file.name.endsWith('.csv')) {
      setError('Please select a CSV file (.csv)')
      return
    }
    setError(null)
    setSelectedFile(file)
    setUploading(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/datasets', {
        method: 'POST',
        body: formData,
      })

      const body = await res.json()

      if (!res.ok) {
        setError(body.detail?.message ?? body.error ?? `Upload failed (${res.status})`)
      } else if (body.error) {
        setError(body.error)
      } else {
        onUploadSuccess(body.data)
        setSelectedFile(null)
        if (inputRef.current) inputRef.current.value = ''
      }
    } catch {
      setError('Network error — is the server running?')
    } finally {
      setUploading(false)
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) handleFileSelect(f)
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled && !uploading) setDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
    if (disabled || uploading) return
    const f = e.dataTransfer.files?.[0]
    if (f) handleFileSelect(f)
  }

  function handleZoneClick() {
    if (!disabled && !uploading) {
      inputRef.current?.click()
    }
  }

  const zoneDisabled = disabled || uploading

  return (
    <div className="space-y-3">
      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleInputChange}
        disabled={zoneDisabled}
      />

      {/* Drag-and-drop zone */}
      <div
        onClick={handleZoneClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          'flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors',
          dragOver
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 bg-white',
          zoneDisabled
            ? 'cursor-not-allowed opacity-50'
            : 'cursor-pointer hover:border-blue-400 hover:bg-blue-50',
        ].join(' ')}
      >
        {uploading ? (
          <>
            <svg className="mb-3 h-8 w-8 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-sm font-medium text-gray-600">
              Uploading {selectedFile?.name}…
            </p>
          </>
        ) : (
          <>
            <svg
              className="mb-3 h-10 w-10 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="text-sm font-medium text-gray-600">
              Drop a CSV here or click to browse
            </p>
            <p className="mt-1 text-xs text-gray-400">Accepts .csv files only</p>
          </>
        )}
      </div>

      {/* Inline error */}
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  )
}
