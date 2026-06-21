'use client';
import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export default function Home() {
  const [datasets, setDatasets] = useState<string[]>([]);
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const sessionRef = useRef<string>('');
  if (!sessionRef.current) {
    sessionRef.current = typeof crypto !== 'undefined'
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  }

  async function uploadFile() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    const name = file.name.replace(/\.[^.]+$/, '').replace(/[^a-z0-9_]/gi, '_').toLowerCase();
    const form = new FormData();
    form.append('file', file);
    form.append('name', name);
    setUploadStatus('Uploading...');
    const res = await fetch(`${API}/datasets/`, { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      setDatasets(prev => [...prev, data.name]);
      setUploadStatus(`Loaded: ${data.name} (${data.row_count} rows, ${data.columns.length} cols)`);
    } else {
      setUploadStatus(`Error: ${data.detail}`);
    }
  }

  async function ask() {
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    const res = await fetch(`${API}/query/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: sessionRef.current }),
    });
    const data = await res.json();
    setResult(data);
    setLoading(false);
  }

  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-2">Analyst</h1>
      <p className="text-gray-500 mb-8">Data analyst agent — ask questions about your datasets</p>

      {/* Upload */}
      <section className="mb-8 p-4 border rounded-lg">
        <h2 className="font-semibold mb-3">Load dataset</h2>
        <div className="flex gap-3">
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.json,.parquet" className="flex-1 text-sm" />
          <button onClick={uploadFile} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Upload
          </button>
        </div>
        {uploadStatus && <p className="mt-2 text-sm text-gray-600">{uploadStatus}</p>}
        {datasets.length > 0 && (
          <p className="mt-2 text-sm">Loaded: {datasets.join(', ')}</p>
        )}
      </section>

      {/* Chat */}
      <section className="mb-8 p-4 border rounded-lg">
        <h2 className="font-semibold mb-3">Ask a question</h2>
        <div className="flex gap-3">
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && ask()}
            placeholder="e.g. show top 10 rows of sales, or plot revenue over product"
            className="flex-1 border rounded px-3 py-2 text-sm"
          />
          <button onClick={ask} disabled={loading} className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50">
            {loading ? 'Thinking...' : 'Ask'}
          </button>
        </div>
      </section>

      {/* Result */}
      {result && (
        <section className="p-4 border rounded-lg">
          <h2 className="font-semibold mb-3">Result</h2>
          <ResultView result={result} />
        </section>
      )}
    </main>
  );
}

function ResultView({ result }: { result: any }) {
  if (result.type === 'table') {
    return (
      <div className="overflow-x-auto">
        <ReactMarkdown
          components={{
            table: (props) => <table className="min-w-full border-collapse text-sm" {...props} />,
            th: (props) => <th className="border px-3 py-1 bg-gray-100 font-semibold text-left" {...props} />,
            td: (props) => <td className="border px-3 py-1" {...props} />,
          }}
        >
          {result.markdown}
        </ReactMarkdown>
      </div>
    );
  }
  if (result.type === 'chart') {
    return <PlotlyChart spec={result.plotly_spec} />;
  }
  return <pre className="text-sm">{JSON.stringify(result, null, 2)}</pre>;
}

function PlotlyChart({ spec }: { spec: any }) {
  const [Plot, setPlot] = useState<any>(null);
  useEffect(() => {
    import('react-plotly.js').then(m => setPlot(() => m.default));
  }, []);
  if (!Plot) return <p className="text-sm text-gray-500">Loading chart...</p>;
  return <Plot data={spec.data} layout={spec.layout} style={{ width: '100%' }} />;
}
