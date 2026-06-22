import React from 'react'
import ResultTable from './ResultTable.jsx'

export default function MessageThread({ messages }) {
  return (
    <div className="space-y-4">
      {messages.map(msg => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-3xl rounded-lg px-4 py-3 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-white border border-gray-200 text-gray-900'
            }`}
          >
            <p className="whitespace-pre-wrap">{msg.content}</p>
            {msg.sql && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs opacity-70 hover:opacity-100">Show SQL</summary>
                <pre className="mt-2 text-xs bg-gray-900 text-green-400 p-2 rounded overflow-x-auto">
                  {msg.sql}
                </pre>
              </details>
            )}
            {msg.results && msg.results.length > 0 && (
              <div className="mt-3">
                <ResultTable rows={msg.results} />
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
