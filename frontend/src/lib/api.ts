import type { Dataset, AuditEntry } from '../types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export async function getDatasets(sessionId: string): Promise<Dataset[]> {
  const res = await fetch(`${BASE}/datasets`, {
    headers: { 'X-Session-ID': sessionId },
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message ?? data.detail ?? `Failed to fetch datasets (${res.status})`)
  }
  return data.data
}

export async function uploadDataset(sessionId: string, file: File): Promise<Dataset> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE}/datasets/upload`, {
    method: 'POST',
    headers: { 'X-Session-ID': sessionId },
    body: formData,
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message ?? data.detail ?? `Upload failed (${res.status})`)
  }
  return data.data
}

export async function query(
  sessionId: string,
  datasetTable: string,
  question: string
): Promise<{ answer: string; table: Record<string, unknown>[]; sql: string; audit_id: string }> {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': sessionId,
    },
    body: JSON.stringify({ question, dataset_table: datasetTable }),
  })
  const data = await res.json()
  if (!res.ok) {
    const detail = data.detail
    const msg =
      typeof detail === 'object' && detail !== null
        ? detail.message ?? JSON.stringify(detail)
        : String(detail ?? `Query failed (${res.status})`)
    throw new Error(msg)
  }
  return data.data
}

export async function getAudit(sessionId: string): Promise<AuditEntry[]> {
  const res = await fetch(`${BASE}/audit`, {
    headers: { 'X-Session-ID': sessionId },
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail?.message ?? data.detail ?? `Failed to fetch audit log (${res.status})`)
  }
  return data.data
}
