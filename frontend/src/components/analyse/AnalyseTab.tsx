'use client'

import { SessionSidebar } from '@/components/analyse/SessionSidebar'
import { TokenWidget } from '@/components/analyse/TokenWidget'
import { TablesCard } from '@/components/analyse/TablesCard'
import { UploadCard } from '@/components/analyse/UploadCard'
import { ConversationCard } from '@/components/analyse/ConversationCard'

/**
 * Analyse tab — Phase-1 labelled stub shell.
 *
 * Two-panel responsive layout: a left sidebar (sessions + token usage) and a
 * main column (tables, upload, conversation). Stacks on narrow viewports.
 * Every child is a clearly-labelled, non-functional placeholder.
 */
export function AnalyseTab() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[20rem_1fr]">
      {/* Sidebar */}
      <aside className="flex flex-col gap-4">
        <SessionSidebar />
        <TokenWidget />
      </aside>

      {/* Main column */}
      <div className="flex flex-col gap-4">
        <TablesCard />
        <UploadCard />
        <ConversationCard />
      </div>
    </div>
  )
}
