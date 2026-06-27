'use client'

import { useEffect, useState } from 'react'
import { api, type SettingsData } from '@/lib/api'

const LLM_MODELS = [
  { value: '', label: 'Default (env)' },
  { value: 'gemini-3.1-flash-lite', label: 'gemini-3.1-flash-lite' },
  { value: 'gemini-1.5-flash', label: 'gemini-1.5-flash' },
  { value: 'gemini-1.5-pro', label: 'gemini-1.5-pro' },
]

export function SettingsPanel({
  open,
  onClose,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  onSaved?: () => void
}) {
  const [form, setForm] = useState<SettingsData>({
    llm_model: null,
    max_iterations: null,
    price_input_per_million: null,
    price_output_per_million: null,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!open) return
    api.getSettings().then(data => setForm(data)).catch(() => {})
  }, [open])

  if (!open) return null

  const set = (key: keyof SettingsData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const val = e.target.value || null
    setForm(prev => ({ ...prev, [key]: val }))
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.patchSettings(form)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      onSaved?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Settings</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={save} className="space-y-4">
          {/* LLM Model */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              LLM Model
            </label>
            <select
              value={form.llm_model ?? ''}
              onChange={set('llm_model')}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {LLM_MODELS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-gray-400">
              Leave &quot;Default&quot; to use the AGENT_LLM_MODEL env var.
            </p>
          </div>

          {/* Max Iterations */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Max iterations
            </label>
            <input
              type="number"
              min={1}
              max={20}
              value={form.max_iterations ?? ''}
              onChange={set('max_iterations')}
              placeholder="Default (env)"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Pricing */}
          <div>
            <p className="mb-2 text-xs font-medium text-gray-700">
              Token pricing (USD per 1M tokens)
            </p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1 block text-[11px] text-gray-500">Input / prompt</label>
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={form.price_input_per_million ?? ''}
                  onChange={set('price_input_per_million')}
                  placeholder="e.g. 0.075"
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] text-gray-500">Output / completion</label>
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={form.price_output_per_million ?? ''}
                  onChange={set('price_output_per_million')}
                  placeholder="e.g. 0.30"
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <p className="mt-1 text-[11px] text-gray-400">
              Used to compute cost in the Token usage widget. Leave blank to show N/A.
            </p>
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saved ? 'Saved!' : saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
