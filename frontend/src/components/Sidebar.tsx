'use client'

import { useEffect, useState } from 'react'
import { getUploads, UploadSummary, UploadResult } from '@/lib/api'

interface SidebarProps {
  activeUploadId: string | null
  onSelectUpload: (upload: UploadResult) => void
  onNewUpload: () => void
  refreshTrigger: number
}

function formatRelativeTime(dateStr: string): string {
  const elapsed = Date.now() - new Date(dateStr).getTime()
  const seconds = Math.floor(elapsed / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days !== 1 ? 's' : ''} ago`
}

export default function Sidebar({ activeUploadId, onSelectUpload, onNewUpload, refreshTrigger }: SidebarProps) {
  const [uploads, setUploads] = useState<UploadSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getUploads()
      .then((data) => {
        setUploads(data)
        setLoading(false)
      })
      .catch((err: Error) => {
        setError(err.message)
        setLoading(false)
      })
  }, [refreshTrigger])

  return (
    <aside className="w-64 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      <div className="px-4 py-4 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">
          Upload History
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {loading && (
          <div className="px-4 py-3 text-sm text-gray-400">Loading…</div>
        )}

        {!loading && error && (
          <div className="px-4 py-3 text-sm text-red-600">{error}</div>
        )}

        {!loading && !error && uploads.length === 0 && (
          <div className="px-4 py-6 text-center">
            <p className="text-sm text-gray-400">No uploads yet. Upload a file to get started.</p>
          </div>
        )}

        {!loading && !error && uploads.length > 0 && (
          <ul className="space-y-1 px-2">
            {uploads.map((upload) => (
              <li key={upload.upload_id}>
                <button
                  onClick={() => onSelectUpload(upload)}
                  className={`w-full text-left rounded-md px-3 py-2.5 transition-colors ${
                    activeUploadId === upload.upload_id
                      ? 'border-l-4 border-l-blue-500 pl-2'
                      : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <p
                    className="text-sm font-medium text-gray-800 truncate"
                    title={upload.filename}
                  >
                    {upload.filename}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {upload.row_count.toLocaleString()} rows &middot; {upload.col_count} cols
                  </p>
                  <p
                    className="text-xs text-gray-400 mt-0.5"
                    title={upload.uploaded_at}
                  >
                    {formatRelativeTime(upload.uploaded_at)}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Always-visible upload button at the bottom */}
      <div className="px-4 py-4 border-t border-gray-200">
        <button
          onClick={onNewUpload}
          className="w-full rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          + Upload New
        </button>
      </div>
    </aside>
  )
}
