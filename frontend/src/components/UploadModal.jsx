import React, { useState, useRef } from 'react'

export default function UploadModal({ onUpload, onClose }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const handleFile = async (file) => {
    setUploading(true)
    setError(null)
    try {
      const data = await onUpload(file)
      setResult(data)
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Upload Dataset</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>

        {result ? (
          <div className="text-center py-4">
            <div className="text-green-600 font-medium">{result.original_filename} uploaded</div>
            <div className="text-sm text-gray-500 mt-1">
              Table: <code>{result.table_name}</code> &middot; {result.row_count.toLocaleString()} rows
            </div>
            <button
              onClick={onClose}
              className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition ${
                dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
              }`}
            >
              {uploading ? (
                <div className="flex flex-col items-center gap-2 text-gray-400">
                  <div className="animate-spin h-8 w-8 border-2 border-gray-300 border-t-blue-600 rounded-full" />
                  <span>Uploading...</span>
                </div>
              ) : (
                <div className="text-gray-500">
                  <p className="font-medium">Drop a file here or click to browse</p>
                  <p className="text-sm mt-1">CSV, JSON, or Parquet &middot; Max 100 MB</p>
                </div>
              )}
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.json,.parquet"
                className="hidden"
                onChange={e => { const f = e.target.files[0]; if (f) handleFile(f) }}
              />
            </div>
            {error && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {error}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
