"use client";

import { useEffect, useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import DatasetSidebar from "@/components/DatasetSidebar";
import { listDatasets, type Dataset } from "@/lib/api";

export default function Home() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    listDatasets()
      .then((d) => setDatasets(d))
      .catch((e) => setLoadError((e as Error).message));
  }, []);

  const selected = datasets.find((d) => d.id === selectedId) || null;

  return (
    <main className="flex h-screen">
      <DatasetSidebar
        datasets={datasets}
        selectedId={selectedId}
        onSelect={(d) => setSelectedId(d.id)}
        onRefresh={(all) => setDatasets(all)}
      />
      {selected ? (
        <ChatPanel dataset={selected} />
      ) : (
        <section className="flex flex-1 items-center justify-center text-slate-400">
          {loadError ? (
            <p className="text-rose-600" data-testid="load-error">
              {loadError}
            </p>
          ) : (
            <p data-testid="empty-state">Create or select a dataset to begin.</p>
          )}
        </section>
      )}
    </main>
  );
}
