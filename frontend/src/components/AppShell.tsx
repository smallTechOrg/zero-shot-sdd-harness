'use client'

import { useState } from 'react'
import { StubBanner } from '@/components/StubBanner'
import { AnalyseTab } from '@/components/analyse/AnalyseTab'
import { DatabaseTab } from '@/components/database/DatabaseTab'

type Tab = 'analyse' | 'database'

/**
 * AppShell — the Phase-1 stub shell for the Data Analysis Agent.
 *
 * Header (app name + tagline + a labelled "Project notes" button + the static
 * yellow stub-mode banner), a two-tab switcher [Analyse] (default) / [Database],
 * and the responsive panel layout for the active tab.
 *
 * Tab switching is purely local UI state (no API call). Every interactive
 * control inside the tabs is a clearly-labelled, non-functional placeholder.
 */
export function AppShell() {
  const [tab, setTab] = useState<Tab>('analyse')

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Static stub-mode banner — shown so demo output is never mistaken for real. */}
      <StubBanner />

      {/* Header */}
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-gray-900">
              Data Analysis Agent
            </h1>
            <p className="text-sm text-gray-500">
              Upload data, ask questions in plain English, get explainable answers.
            </p>
          </div>
          <button
            type="button"
            disabled
            aria-disabled="true"
            title="Coming in Phase 3"
            className="cursor-not-allowed rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-medium text-gray-400"
          >
            Project notes
          </button>
        </div>

        {/* Tab switcher (local UI state — allowed in Phase 1) */}
        <div className="mx-auto max-w-6xl px-4">
          <div role="tablist" aria-label="Views" className="flex gap-1">
            <TabButton
              id="tab-analyse"
              label="Analyse"
              active={tab === 'analyse'}
              onClick={() => setTab('analyse')}
            />
            <TabButton
              id="tab-database"
              label="Database"
              active={tab === 'database'}
              onClick={() => setTab('database')}
            />
          </div>
        </div>
      </header>

      {/* Active tab */}
      <main className="mx-auto max-w-6xl px-4 py-6">
        <div
          role="tabpanel"
          id="panel-analyse"
          aria-labelledby="tab-analyse"
          hidden={tab !== 'analyse'}
        >
          {tab === 'analyse' && <AnalyseTab />}
        </div>
        <div
          role="tabpanel"
          id="panel-database"
          aria-labelledby="tab-database"
          hidden={tab !== 'database'}
        >
          {tab === 'database' && <DatabaseTab />}
        </div>
      </main>
    </div>
  )
}

function TabButton({
  id,
  label,
  active,
  onClick,
}: {
  id: string
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      id={id}
      role="tab"
      aria-selected={active}
      aria-controls={`panel-${label.toLowerCase()}`}
      onClick={onClick}
      className={`-mb-px rounded-t-md border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? 'border-blue-600 text-blue-700'
          : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
    >
      {label}
    </button>
  )
}
