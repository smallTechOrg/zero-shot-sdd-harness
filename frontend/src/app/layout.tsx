import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Local CSV Analyst',
  description: 'Upload a CSV, ask in plain English, watch the agent write & run pandas locally.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  )
}
