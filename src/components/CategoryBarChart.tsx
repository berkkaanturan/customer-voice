"use client";

import type { CategoryDist } from "./Dashboard";

interface Props {
  data: CategoryDist[];
}

export default function CategoryBarChart({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-on-surface-variant text-xs font-medium">
        Kategori verisi yok
      </div>
    );
  }

  const maxCount = data[0]?.count || 1;

  return (
    <div className="space-y-4">
      {data.map((cat) => (
        <div key={cat.name} className="group">
          {/* Label Row */}
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-bold text-on-surface tracking-tight">{cat.name}</span>
            <span className="text-xs font-semibold text-on-surface-variant opacity-80">{cat.count} reviews</span>
          </div>
          {/* Progress Bar Track */}
          <div className="w-full bg-[#f3ebf6] h-[6px] rounded-full overflow-hidden">
            <div
              className="bg-primary h-full rounded-full animate-grow"
              style={{ width: `${Math.max(5, (cat.count / maxCount) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
