'use client'

import { useState, useRef, useEffect } from 'react'
import type { Dataset, QueryResult } from '../types'
import { query as apiQuery } from '../lib/api'
import StubCard from './StubCard'

interface Props {
  selectedDataset: Dataset | null
  sessionId: string
  queryHistory: QueryResult[]
  onQueryComplete: (result: QueryResult) => void
  isQuerying: boolean
  setIsQuerying: (v: boolean) => void
}

function ResultTable({ table }: { table: Record<string, unknown>[] }) {
  if (table.length === 0) return null
  const cols = Object.keys(table[0])
  return (
    <div className="overflow-x-auto mt-4">
      <table className="min-w-full text-sm border-collapse">
        <thead>
          <tr>
            {cols.map((col) => (
              <th
                key={col}
                className="border border-gray-200 px-3 py-2 bg-gray-100 text-left font-semibold text-gray-700"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              {cols.map((col, j) => {
                const val = row[col]
                return (
                  <td key={j} className="border border-gray-200 px-3 py-2 text-gray-700">
                    {val === null || val === undefined ? (
                      <span className="text-gray-400 italic">—</span>
                    ) : (
                      String(val)
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function QueryHistoryItem({ item }: { item: QueryResult }) {
  return (
    <div className="space-y-3">
      {/* User question */}
      <div className="flex justify-end">
        <div className="max-w-lg rounded-2xl bg-blue-600 px-4 py-2 text-sm text-white">
          {item.question}
        </div>
      </div>

      {/* Assistant answer */}
      <div className="flex justify-start">
        <div className="max-w-2xl w-full rounded-2xl bg-white border border-gray-200 px-4 py-3 shadow-sm">
          {/* Answer text */}
          {item.answer && (
            <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {item.answer}
            </div>
          )}

          {/* Result table */}
          {item.table && item.table.length > 0 && <ResultTable table={item.table} />}

          {/* SQL collapsible */}
          {item.sql && (
            <details className="mt-2 text-xs text-gray-500">
              <summary className="cursor-pointer select-none hover:text-gray-700">View SQL</summary>
              <pre className="mt-1 p-2 bg-gray-100 rounded overflow-x-auto font-mono text-xs">
                {item.sql}
              </pre>
            </details>
          )}

          {/* Timestamp */}
          <p className="text-xs text-gray-400 mt-2">
            {new Date(item.timestamp).toLocaleTimeString()}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function QueryPanel({
  selectedDataset,
  sessionId,
  queryHistory,
  onQueryComplete,
  isQuerying,
  setIsQuerying,
}: Props) {
  const [question, setQuestion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom when history changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [queryHistory, isQuerying])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || !selectedDataset || isQuerying) return

    const q = question.trim()
    setQuestion('')
    setError(null)
    setIsQuerying(true)

    try {
      const result = await apiQuery(sessionId, selectedDataset.table_name, q)
      const queryResult: QueryResult = {
        id: result.audit_id,
        question: q,
        answer: result.answer,
        table: result.table,
        sql: result.sql,
        timestamp: new Date().toISOString(),
      }
      onQueryComplete(queryResult)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Query failed. Please try again.')
    } finally {
      setIsQuerying(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as React.FormEvent)
    }
  }

  const noDataset = !selectedDataset

  return (
    <div className="flex flex-col h-full">
      {/* Chat history area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {queryHistory.length === 0 && !isQuerying && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
            {noDataset ? (
              <>
                <p className="text-base font-medium text-gray-500">Select a dataset to start</p>
                <p className="text-sm">
                  Choose a dataset from the sidebar to begin querying your data.
                </p>
              </>
            ) : (
              <>
                <p className="text-base font-medium text-gray-500">
                  Ask anything about{' '}
                  <span className="text-gray-700">{selectedDataset.original_filename}</span>
                </p>
                <p className="text-sm">
                  Example: &ldquo;What are the top 5 rows by value?&rdquo;
                </p>
              </>
            )}
          </div>
        )}

        {queryHistory.map((item) => (
          <QueryHistoryItem key={item.id} item={item} />
        ))}

        {/* Loading indicator while querying */}
        {isQuerying && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-white border border-gray-200 px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-sm text-blue-500">
                <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                <em>Analysing your question…</em>
              </div>
            </div>
          </div>
        )}

        {/* Query error */}
        {error && (
          <div className="flex justify-start">
            <div className="max-w-2xl w-full rounded-2xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              <strong>Error:</strong> {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Stub cards below response area — always visible */}
      <div className="px-4 pb-2 space-y-2 shrink-0">
        <StubCard title="Charts" comingIn="Phase 2" />
        <StubCard title="Dashboards" comingIn="Phase 3" />
      </div>

      {/* Input bar */}
      <div className="border-t border-gray-200 px-4 py-3 shrink-0">
        <form onSubmit={handleSubmit} className="flex gap-2 items-center">
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isQuerying || noDataset}
            placeholder={
              noDataset
                ? 'Select a dataset from the sidebar to start querying'
                : isQuerying
                  ? 'Analysing…'
                  : `Ask a question about ${selectedDataset?.original_filename ?? 'your data'}…`
            }
            className="flex-1 rounded-xl border border-gray-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={isQuerying || noDataset || !question.trim()}
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shrink-0 transition-colors"
          >
            {isQuerying ? 'Analysing…' : 'Send'}
          </button>
        </form>
        {noDataset && (
          <p className="text-xs text-gray-400 mt-1.5 text-center">
            Select a dataset from the left sidebar to enable querying
          </p>
        )}
      </div>
    </div>
  )
}
