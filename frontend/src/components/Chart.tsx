'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ChartPayload } from '../lib/api'

const COLORS = ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626', '#0891b2', '#db2777', '#65a30d']

export function Chart({ chart }: { chart: ChartPayload | null }) {
  // Table-only / missing chart: render nothing here (SummaryTable carries it).
  if (!chart || chart.type === 'table' || !chart.data || chart.data.length === 0) {
    return null
  }

  const x = chart.x ?? Object.keys(chart.data[0])[0]
  const y = chart.y ?? Object.keys(chart.data[0])[1]
  if (!x || !y) return null

  return (
    <div data-testid="chart" data-chart-type={chart.type} className="rounded-lg border border-gray-100 bg-white p-2">
      <ResponsiveContainer width="100%" height={280}>
        {chart.type === 'line' ? (
          <LineChart data={chart.data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
            <XAxis dataKey={x} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line type="monotone" dataKey={y} stroke="#2563eb" strokeWidth={2} dot={false} />
          </LineChart>
        ) : chart.type === 'pie' ? (
          <PieChart>
            <Pie data={chart.data} dataKey={y} nameKey={x} cx="50%" cy="50%" outerRadius={100} label>
              {chart.data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        ) : (
          <BarChart data={chart.data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
            <XAxis dataKey={x} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey={y} radius={[4, 4, 0, 0]}>
              {chart.data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
