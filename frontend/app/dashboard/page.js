'use client';
import { useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// [C-PLOTLY-SSR]: never import at top level — use dynamic with ssr:false
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export default function DashboardPage() {
  const [sessionId, setSessionId] = useState('');
  const [panels, setPanels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [inputSession, setInputSession] = useState('');

  // [C-SSR-BROWSER-API]: read localStorage inside useEffect only
  useEffect(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem('analyst_session_id') : '';
    if (stored) {
      setSessionId(stored);
      setInputSession(stored);
    }
  }, []);

  const loadDashboard = useCallback(async (sid) => {
    if (!sid) return;
    setLoading(true);
    try {
      const r = await fetch(`${API}/dashboard/${sid}`);
      const j = await r.json();
      if (j.ok) setPanels(j.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (sessionId) loadDashboard(sessionId);
  }, [sessionId, loadDashboard]);

  const removePanel = async (panelId) => {
    await fetch(`${API}/dashboard/${sessionId}/panels/${panelId}`, { method: 'DELETE' });
    setPanels(prev => prev.filter(p => p.id !== panelId));
  };

  const renderPanel = (panel) => {
    if (panel.panel_type === 'chart' && panel.chart_spec) {
      try {
        const spec = typeof panel.chart_spec === 'string' ? JSON.parse(panel.chart_spec) : panel.chart_spec;
        return <Plot data={spec.data || []} layout={{ ...(spec.layout || {}), autosize: true }} style={{ width: '100%', height: 280 }} useResizeHandler />;
      } catch { /* fall through to text */ }
    }
    return <ReactMarkdown remarkPlugins={[remarkGfm]}>{panel.answer || ''}</ReactMarkdown>;
  };

  return (
    <main style={{ fontFamily: 'system-ui', maxWidth: 1100, margin: '0 auto', padding: '1.5rem' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Dashboard</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: '1rem' }}>
        <input
          value={inputSession}
          onChange={e => setInputSession(e.target.value)}
          placeholder="Session ID"
          style={{ flex: 1, padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 14 }}
        />
        <button
          onClick={() => setSessionId(inputSession)}
          style={{ padding: '6px 14px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
        >
          Load
        </button>
        <a href="/" style={{ padding: '6px 14px', background: '#f3f4f6', color: '#374151', borderRadius: 6, textDecoration: 'none', lineHeight: '1.8' }}>
          Back to Chat
        </a>
      </div>

      {loading && <p style={{ color: '#6b7280' }}>Loading panels...</p>}
      {!loading && panels.length === 0 && sessionId && (
        <p style={{ color: '#6b7280' }}>No pinned panels yet. Pin a query result from the chat.</p>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: '1rem' }}>
        {panels.map(panel => (
          <div key={panel.id} style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: '1rem', background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#111827' }}>{panel.title || panel.query_text}</h3>
              <button
                onClick={() => removePanel(panel.id)}
                style={{ background: 'none', border: 'none', color: '#dc2626', cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: 0 }}
                title="Remove panel"
              >x</button>
            </div>
            <div style={{ fontSize: 14, color: '#374151' }}>{renderPanel(panel)}</div>
            <p style={{ margin: '0.5rem 0 0', fontSize: 12, color: '#9ca3af' }}>{new Date(panel.created_at).toLocaleString()}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
