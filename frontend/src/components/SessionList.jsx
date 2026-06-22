import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSessions } from '../hooks/useSessions.js'

export default function SessionList() {
  const navigate = useNavigate()
  const { sessions, loading, error, createSession } = useSessions()
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    setCreating(true)
    try {
      const session = await createSession('New Session')
      navigate(`/${session.session_id}`)
    } catch (err) {
      alert('Failed to create session: ' + (err.message || 'Unknown error'))
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Loading sessions...</div>

  return (
    <div className="max-w-3xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Data Analyst Sessions</h1>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {creating ? 'Creating...' : '+ New Session'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded text-red-700">
          {error}
        </div>
      )}

      {sessions.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">No sessions yet</p>
          <p className="text-sm mt-1">Click &ldquo;New Session&rdquo; to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map(session => (
            <div
              key={session.session_id}
              onClick={() => navigate(`/${session.session_id}`)}
              className="p-4 bg-white border border-gray-200 rounded-lg cursor-pointer hover:border-blue-400 hover:shadow-sm transition"
            >
              <div className="font-medium text-gray-900">{session.title}</div>
              <div className="text-sm text-gray-500 mt-1">
                {session.dataset_count} dataset{session.dataset_count !== 1 ? 's' : ''} &middot;{' '}
                {session.message_count} message{session.message_count !== 1 ? 's' : ''} &middot;{' '}
                {new Date(session.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
