"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { SentimentDist } from "./Dashboard";
import type { PieLabelRenderProps } from "recharts";

const COLORS: Record<string, string> = {
  Pozitif: "#16a34a", // Emerald-600
  Negatif: "#dc2626", // Red-600
  Nötr: "#d97706",    // Amber-600
};

interface Props {
  data: SentimentDist;
}

const RADIAN = Math.PI / 180;
const renderCustomizedLabel = (props: PieLabelRenderProps) => {
  const cx = Number(props.cx ?? 0);
  const cy = Number(props.cy ?? 0);
  const midAngle = Number(props.midAngle ?? 0);
  const innerRadius = Number(props.innerRadius ?? 0);
  const outerRadius = Number(props.outerRadius ?? 0);
  const percent = Number(props.percent ?? 0);

  if (percent < 0.05) return null;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      className="text-[11px] font-bold font-mono"
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

export default function SentimentPieChart({ data }: Props) {
  const chartData = [
    { name: "Pozitif", value: data.Positive },
    { name: "Negatif", value: data.Negative },
    { name: "Nötr", value: data.Neutral },
  ].filter((d) => d.value > 0);

  const total = chartData.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-[260px] text-text-muted text-xs">
        Analiz edilecek veri yok
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={renderCustomizedLabel}
          outerRadius={100}
          innerRadius={60}
          paddingAngle={3}
          dataKey="value"
          animationBegin={0}
          animationDuration={600}
          animationEasing="ease-out"
          stroke="none"
        >
          {chartData.map((entry) => (
            <Cell
              key={entry.name}
              fill={COLORS[entry.name]}
            />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "rgba(255, 255, 255, 0.98)",
            border: "1px solid rgba(226, 232, 240, 0.8)",
            borderRadius: "16px",
            padding: "10px 14px",
            boxShadow: "0 20px 40px -15px rgba(15, 23, 42, 0.08)",
          }}
          itemStyle={{ color: "#0f172a", fontSize: "12px", fontFamily: "var(--font-sans)" }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any, name: any) => [
            `${value} yorum (${total > 0 ? ((Number(value) / total) * 100).toFixed(1) : 0}%)`,
            String(name),
          ]}
        />
        <Legend
          verticalAlign="bottom"
          iconType="circle"
          iconSize={6}
          formatter={(value: string) => (
            <span className="text-[11px] font-semibold text-text-muted px-1">{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
