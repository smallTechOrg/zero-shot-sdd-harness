import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Data Analyst Agent',
  description: 'Upload a CSV and ask questions in natural language.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen overflow-hidden bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  )
}
