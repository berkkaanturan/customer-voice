"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { SentimentDist } from "./Dashboard";

interface Props {
  data: SentimentDist;
}

export default function SentimentPieChart({ data }: Props) {
  const total = data.Positive + data.Negative;

  if (total === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-on-surface-variant text-xs">
        Analiz edilecek veri yok
      </div>
    );
  }

  const negPercent = Math.round((data.Negative / total) * 100);
  const posPercent = 100 - negPercent;

  const chartData = [
    { name: "Pozitif", value: data.Positive, percent: posPercent, color: "#10B981" },
    { name: "Negatif", value: data.Negative, percent: negPercent, color: "#EF4444" },
  ];

  return (
    <div className="flex flex-col items-center justify-between w-full h-full pt-4 relative">
      <div className="w-full h-48 relative flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              paddingAngle={3}
              dataKey="value"
              animationBegin={0}
              animationDuration={500}
              stroke="none"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "rgba(255, 255, 255, 0.98)",
                border: "1px solid rgba(226, 232, 240, 0.8)",
                borderRadius: "12px",
                padding: "8px 12px",
                boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
              }}
              itemStyle={{ fontSize: "12px", fontWeight: "600", fontFamily: "Inter, sans-serif" }}
              formatter={(value: any, name: any, props: any) => {
                const percent = props.payload.percent;
                return [`${value} yorum (${percent}%)`, name];
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        
        {/* Absolute Center Text */}
        <div className="absolute flex flex-col items-center justify-center pointer-events-none">
          <span className="text-[28px] font-bold text-[#220053] leading-none">{posPercent}%</span>
          <span className="text-xs text-on-surface-variant font-medium mt-1">Pozitif</span>
        </div>
      </div>

      {/* Legend separator */}
      <div className="w-full border-t border-outline-variant/30 mt-6 pt-4 flex items-center justify-center gap-6">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-[#10B981]" />
          <span className="text-xs font-semibold text-on-surface-variant">Pozitif</span>
          <span className="text-sm font-bold text-[#220053]">{posPercent}%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-[#EF4444]" />
          <span className="text-xs font-semibold text-on-surface-variant">Negatif</span>
          <span className="text-sm font-bold text-[#220053]">{negPercent}%</span>
        </div>
      </div>
    </div>
  );
}
