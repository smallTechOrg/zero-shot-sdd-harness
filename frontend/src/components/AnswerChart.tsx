'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Area,
  AreaChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ChartSpec } from '@/lib/api'

const PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899']

interface Props {
  chart: ChartSpec
}

// Renders the agent-picked chart interactively (hover tooltip, legend, responsive zoom-to-fit).
export default function AnswerChart({ chart }: Props) {
  const data = Array.isArray(chart.data) ? chart.data : []
  if (data.length === 0) {
    return (
      <div
        data-testid="chart-empty"
        className="flex h-48 items-center justify-center rounded-lg border border-dashed border-slate-200 text-xs text-slate-400"
      >
        No chart data for this answer
      </div>
    )
  }

  const x = chart.x ?? inferX(data)
  const ys = normaliseY(chart.y, data, x)
  const type = (chart.type ?? 'bar').toLowerCase()

  return (
    <div data-testid="answer-chart" className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {renderChart(type, data, x, ys)}
      </ResponsiveContainer>
    </div>
  )
}

function renderChart(type: string, data: Array<Record<string, unknown>>, x: string, ys: string[]) {
  const common = {
    data,
    margin: { top: 8, right: 16, left: 0, bottom: 8 },
  }
  const axes = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
      <XAxis dataKey={x} tick={{ fontSize: 11 }} stroke="#94a3b8" />
      <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
      <Tooltip
        contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
        cursor={{ fill: 'rgba(99,102,241,0.06)' }}
      />
      {ys.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
    </>
  )

  switch (type) {
    case 'line':
      return (
        <LineChart {...common}>
          {axes}
          {ys.map((y, i) => (
            <Line
              key={y}
              type="monotone"
              dataKey={y}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={{ r: 2 }}
              activeDot={{ r: 5 }}
            />
          ))}
        </LineChart>
      )
    case 'area':
      return (
        <AreaChart {...common}>
          {axes}
          {ys.map((y, i) => (
            <Area
              key={y}
              type="monotone"
              dataKey={y}
              stroke={PALETTE[i % PALETTE.length]}
              fill={PALETTE[i % PALETTE.length]}
              fillOpacity={0.2}
            />
          ))}
        </AreaChart>
      )
    case 'scatter':
      return (
        <ScatterChart {...common}>
          {axes}
          <Scatter data={data} fill={PALETTE[0]} dataKey={ys[0]} />
        </ScatterChart>
      )
    case 'pie':
      return (
        <PieChart>
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Pie data={data} dataKey={ys[0]} nameKey={x} outerRadius={100} label>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
        </PieChart>
      )
    case 'bar':
    default:
      return (
        <BarChart {...common}>
          {axes}
          {ys.map((y, i) => (
            <Bar key={y} dataKey={y} fill={PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      )
  }
}

function inferX(data: Array<Record<string, unknown>>): string {
  const keys = Object.keys(data[0] ?? {})
  // first non-numeric key, else first key
  const cat = keys.find(k => typeof data[0][k] !== 'number')
  return cat ?? keys[0] ?? 'name'
}

function normaliseY(
  y: string | string[] | undefined,
  data: Array<Record<string, unknown>>,
  x: string,
): string[] {
  if (Array.isArray(y) && y.length) return y
  if (typeof y === 'string' && y) return [y]
  // infer: all numeric keys except x
  const keys = Object.keys(data[0] ?? {})
  const numeric = keys.filter(k => k !== x && typeof data[0][k] === 'number')
  return numeric.length ? numeric : keys.filter(k => k !== x)
}
