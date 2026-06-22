'use client'

import { useState } from 'react'
import type { ApiMessage } from '../lib/api'
import ResultTable from './ResultTable'
import StubButton from './StubBadge'

export default function MessageBubble({ message }: { message: ApiMessage }) {
  const [showSql, setShowSql] = useState(false)
  const isUser = message.role === 'user'
  const isError = !isUser && message.sql == null && message.result == null &&
    /failed|couldn't|error/i.test(message.content)

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[90%] rounded-2xl rounded-bl-sm border px-4 py-3 text-sm ${
          isError
            ? 'border-red-200 bg-red-50 text-red-700'
            : 'border-gray-200 bg-white text-gray-900'
        }`}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>

        {message.result && <ResultTable result={message.result} />}

        {message.sql && (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => setShowSql(s => !s)}
              className="text-xs font-medium text-blue-600 hover:underline"
            >
              {showSql ? 'Hide SQL' : 'View SQL'}
            </button>
            {showSql && (
              <pre className="mt-2 overflow-auto rounded-md bg-gray-900 px-3 py-2 text-xs text-gray-100">
                {message.sql}
              </pre>
            )}
          </div>
        )}

        {message.result && (
          <div className="mt-3 flex gap-2">
            <StubButton label="Chart" className="!w-auto" />
            <StubButton label="Dashboard" className="!w-auto" />
          </div>
        )}
      </div>
    </div>
  )
}
