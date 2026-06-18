"use client";

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
} from "recharts";

import type { ChartSpec } from "@/lib/api";

const COLORS = ["#2563eb", "#16a34a", "#db2777", "#d97706", "#7c3aed", "#0891b2"];

export default function ChartView({ chart }: { chart: ChartSpec }) {
  const data = chart.data.map((d) => ({ x: String(d.x), y: Number(d.y) }));

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3" data-testid="chart">
      {chart.title ? (
        <div className="mb-2 text-sm font-medium text-slate-700">{chart.title}</div>
      ) : null}
      <ResponsiveContainer width="100%" height={260}>
        {chart.type === "line" ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" /> <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="y" name={chart.y} stroke={COLORS[0]} />
          </LineChart>
        ) : chart.type === "pie" ? (
          <PieChart>
            <Tooltip />
            <Legend />
            <Pie data={data} dataKey="y" nameKey="x" outerRadius={100} label>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" /> <YAxis />
            <Tooltip />
            <Bar dataKey="y" name={chart.y} fill={COLORS[0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
