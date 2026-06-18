"use client";

import { useRef, useState } from "react";

import {
  createDataset,
  listDatasets,
  uploadFiles,
  type Dataset,
} from "@/lib/api";

export default function DatasetSidebar({
  datasets,
  selectedId,
  onSelect,
  onRefresh,
}: {
  datasets: Dataset[];
  selectedId: string | null;
  onSelect: (d: Dataset) => void;
  onRefresh: (datasets: Dataset[]) => void;
}) {
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const selected = datasets.find((d) => d.id === selectedId) || null;

  async function handleCreate() {
    if (!newName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const ds = await createDataset(newName.trim());
      setNewName("");
      const all = await listDatasets();
      onRefresh(all);
      onSelect(ds);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(files: FileList | null) {
    if (!files || !selected) return;
    setBusy(true);
    setError(null);
    try {
      await uploadFiles(selected.id, Array.from(files));
      onRefresh(await listDatasets());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <aside className="flex w-80 flex-col gap-4 border-r border-slate-200 bg-white p-4">
      <h1 className="text-lg font-semibold">DataChat</h1>

      <div className="space-y-2">
        <div className="flex gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            placeholder="New dataset name"
            data-testid="new-dataset-name"
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          <button
            onClick={handleCreate}
            disabled={busy || !newName.trim()}
            data-testid="create-dataset"
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto" data-testid="dataset-list">
        {datasets.map((d) => (
          <button
            key={d.id}
            onClick={() => onSelect(d)}
            className={`block w-full rounded-md px-2 py-1.5 text-left text-sm ${
              d.id === selectedId ? "bg-blue-50 text-blue-700" : "hover:bg-slate-100"
            }`}
          >
            <div className="font-medium">{d.name}</div>
            <div className="text-xs text-slate-500">
              {d.files.length} file{d.files.length === 1 ? "" : "s"}
            </div>
          </button>
        ))}
        {datasets.length === 0 ? (
          <p className="px-2 py-1.5 text-sm text-slate-400">No datasets yet.</p>
        ) : null}
      </div>

      {selected ? (
        <div className="space-y-2 border-t border-slate-200 pt-3">
          <div className="text-xs font-medium text-slate-500">UPLOAD CSV TO “{selected.name}”</div>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            multiple
            data-testid="file-input"
            onChange={(e) => handleUpload(e.target.files)}
            className="block w-full text-sm"
          />
          {selected.files.map((f) => (
            <div key={f.id} className="text-xs text-slate-500">
              {f.filename} — {f.row_count} rows, {f.schema_columns.length} cols
            </div>
          ))}
        </div>
      ) : null}

      {error ? (
        <p className="text-xs text-rose-600" data-testid="sidebar-error">
          {error}
        </p>
      ) : null}
      {busy ? <p className="text-xs text-slate-400">Working…</p> : null}
    </aside>
  );
}
