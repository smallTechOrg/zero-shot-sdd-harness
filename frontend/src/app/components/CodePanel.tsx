'use client'

export default function CodePanel({ code }: { code: string | null }) {
  if (!code) return null
  return (
    <details className="group rounded-lg border border-gray-200 bg-gray-50" data-testid="code-panel">
      <summary className="cursor-pointer select-none px-4 py-2.5 text-sm font-medium text-gray-700 hover:text-gray-900">
        Show code
      </summary>
      <pre
        data-testid="code-block"
        className="overflow-x-auto border-t border-gray-200 bg-gray-900 p-4 text-xs leading-relaxed text-gray-100"
      >
        <code>{code}</code>
      </pre>
    </details>
  )
}
