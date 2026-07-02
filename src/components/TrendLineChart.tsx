"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
  Legend,
} from "recharts";
import { useState } from "react";
import type { TrendPoint } from "./Dashboard";

interface Props {
  data: TrendPoint[];
}

export default function TrendLineChart({ data }: Props) {
  const [hoveredSeries, setHoveredSeries] = useState<string | null>(null);

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-[260px] text-text-muted text-xs">
        Trend analizi için yeterli veri yok
      </div>
    );
  }

  return (
    <ResponsiveContainer width="99%" height={260} minWidth={1} minHeight={1}>
      <ComposedChart data={data}>
        <defs>
          <linearGradient id="totalGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity={0.06} />
            <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(226, 232, 240, 0.5)"
          vertical={false}
        />
        <XAxis
          dataKey="label"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 10, fill: "#94a3b8", fontFamily: "var(--font-sans)" }}
          interval="preserveStartEnd"
          minTickGap={45}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 10, fill: "#94a3b8", fontFamily: "var(--font-mono)" }}
          allowDecimals={false}
          width={25}
        />
        <Tooltip
          contentStyle={{
            background: "rgba(255, 255, 255, 0.98)",
            border: "1px solid rgba(226, 232, 240, 0.8)",
            borderRadius: "16px",
            padding: "10px 14px",
            boxShadow: "0 20px 40px -15px rgba(15, 23, 42, 0.08)",
          }}
          labelStyle={{ color: "#0f172a", fontSize: "11px", fontWeight: 700, fontFamily: "var(--font-sans)", marginBottom: "4px" }}
          itemStyle={{ fontSize: "11px", fontFamily: "var(--font-sans)", padding: "1px 0" }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any, name: any) => {
            const nameMap: Record<string, string> = {
              total: "Toplam",
              positive: "Pozitif",
              negative: "Negatif",
            };
            return [value, nameMap[String(name)] || name];
          }}
        />
        <Legend
          verticalAlign="top"
          align="right"
          iconType="circle"
          iconSize={6}
          wrapperStyle={{ fontSize: "10px", fontWeight: 600, paddingBottom: "12px", fontFamily: "var(--font-sans)" }}
          onMouseEnter={(o) => setHoveredSeries(o.dataKey as string)}
          onMouseLeave={() => setHoveredSeries(null)}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any) => {
            const nameMap: Record<string, string> = {
              total: "Toplam Yorum",
              positive: "Pozitif",
              negative: "Negatif",
            };
            return (
              <span className="text-text-muted px-1">{nameMap[value] || value}</span>
            );
          }}
        />
        <Area
          type="monotone"
          dataKey="total"
          fill="url(#totalGradient)"
          stroke="#2563eb"
          strokeWidth={hoveredSeries === "total" ? 3 : 2}
          strokeOpacity={hoveredSeries === null || hoveredSeries === "total" ? 1 : 0.15}
          fillOpacity={hoveredSeries === null || hoveredSeries === "total" ? 1 : 0.15}
          dot={false}
          activeDot={{ r: 4, fill: "#2563eb", stroke: "#ffffff", strokeWidth: 2 }}
          animationDuration={600}
        />
        <Line
          type="monotone"
          dataKey="positive"
          stroke="#16a34a"
          strokeWidth={hoveredSeries === "positive" ? 2.5 : 1.5}
          strokeOpacity={hoveredSeries === null || hoveredSeries === "positive" ? 1 : 0.15}
          dot={false}
          strokeDasharray="4 4"
          animationDuration={800}
        />
        <Line
          type="monotone"
          dataKey="negative"
          stroke="#dc2626"
          strokeWidth={hoveredSeries === "negative" ? 2.5 : 1.5}
          strokeOpacity={hoveredSeries === null || hoveredSeries === "negative" ? 1 : 0.15}
          dot={false}
          strokeDasharray="4 4"
          animationDuration={800}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
