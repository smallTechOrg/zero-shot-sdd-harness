'use client'

import { useState } from 'react'

interface CodeAccordionProps {
  code: string
}

export default function CodeAccordion({ code }: CodeAccordionProps) {
  const [open, setOpen] = useState(false)

  return (
    <section
      aria-label="Generated code"
      data-testid="code-accordion"
      className="rounded-xl border border-gray-200 bg-white shadow-sm"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-xl px-5 py-4 text-left text-sm font-medium text-gray-900 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <span>{open ? 'Hide code' : 'Show code'}</span>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.17l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {open && (
        <div className="border-t border-gray-100 p-4">
          <pre
            data-testid="code-block"
            className="overflow-x-auto rounded-lg bg-gray-900 p-4 font-mono text-xs leading-relaxed text-gray-100"
          >
            <code>{code}</code>
          </pre>
        </div>
      )}
    </section>
  )
}
