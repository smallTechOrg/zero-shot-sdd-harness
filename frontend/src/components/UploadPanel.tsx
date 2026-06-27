'use client'

import { useState, useRef, DragEvent, ChangeEvent } from 'react'
import { uploadFile, UploadResult } from '@/lib/api'

interface UploadPanelProps {
  onUploadSuccess: (result: UploadResult) => void
}

const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx', '.xls']
const ACCEPTED_MIME_TYPES = [
  'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
]

function isValidFile(file: File): boolean {
  const name = file.name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

export default function UploadPanel({ onUploadSuccess }: UploadPanelProps) {
  const [dragging, setDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<UploadResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(true)
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileSelected(file)
  }

  function handleFileInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFileSelected(file)
  }

  function handleFileSelected(file: File) {
    if (!isValidFile(file)) {
      setError(`Unsupported file type. Please upload a .csv, .xlsx, or .xls file.`)
      setSelectedFile(null)
      return
    }
    setError(null)
    setResult(null)
    setSelectedFile(file)
  }

  async function handleUpload() {
    if (!selectedFile) return
    setUploading(true)
    setError(null)
    try {
      const uploadResult = await uploadFile(selectedFile)
      setResult(uploadResult)
      onUploadSuccess(uploadResult)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed. Please try again.'
      setError(message)
    } finally {
      setUploading(false)
    }
  }

  function handleBrowseClick() {
    fileInputRef.current?.click()
  }

  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Upload a File</h2>

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`rounded-xl border-2 border-dashed p-12 text-center transition-colors cursor-pointer ${
          dragging
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 bg-gray-50 hover:border-blue-300 hover:bg-blue-50'
        }`}
        onClick={handleBrowseClick}
        role="button"
        aria-label="Drop zone — click or drag and drop a CSV or Excel file"
      >
        <div className="flex flex-col items-center gap-3">
          <svg
            className="w-12 h-12 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <div>
            <p className="text-sm font-medium text-gray-700">
              Drag &amp; drop your file here, or{' '}
              <span className="text-blue-600 hover:underline">browse</span>
            </p>
            <p className="text-xs text-gray-400 mt-1">Supports .csv, .xlsx, .xls (max 50 MB)</p>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept={[...ACCEPTED_EXTENSIONS, ...ACCEPTED_MIME_TYPES].join(',')}
          className="hidden"
          onChange={handleFileInputChange}
          aria-hidden="true"
        />
      </div>

      {/* Selected file preview */}
      {selectedFile && !result && (
        <div className="mt-4 flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <span className="text-sm text-gray-700 font-medium">{selectedFile.name}</span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleUpload()
            }}
            disabled={uploading}
            className="ml-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {uploading ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Uploading…
              </span>
            ) : (
              'Upload'
            )}
          </button>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p>{error}</p>
          <button
            onClick={() => {
              setError(null)
              setSelectedFile(null)
            }}
            className="mt-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Success state */}
      {result && (
        <div className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-4">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-green-600 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-green-800">{result.filename} uploaded successfully</p>
              <p className="text-xs text-green-700 mt-1">
                {result.row_count.toLocaleString()} rows &middot; {result.col_count} columns
              </p>
              <div className="mt-2">
                <p className="text-xs text-green-700 font-medium mb-1">Columns:</p>
                <div className="flex flex-wrap gap-1">
                  {result.columns.map((col) => (
                    <span
                      key={col.name}
                      className="inline-block rounded bg-green-100 px-2 py-0.5 text-xs text-green-800"
                    >
                      {col.name}
                      <span className="text-green-600 ml-1">({col.dtype})</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
