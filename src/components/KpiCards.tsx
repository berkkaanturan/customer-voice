"use client";

import type { KpiData } from "./Dashboard";
import { 
  ChatTeardropText, 
  UserMinus, 
  Shapes, 
  TrendUp, 
  TrendDown 
} from "@phosphor-icons/react";

interface KpiCardsProps {
  kpi: KpiData;
  loading: boolean;
}

export default function KpiCards({ kpi, loading }: KpiCardsProps) {
  // Dynamically calculate top category percentage of total complaints
  const topCategoryPct =
    kpi.totalCount > 0
      ? Math.round((kpi.topCategory.count / kpi.totalCount) * 100)
      : 35;

  const cards = [
    {
      title: "Toplam Yorum Hacmi",
      value: kpi.totalCount.toLocaleString("tr-TR"),
      icon: <ChatTeardropText size={24} weight="duotone" />,
      iconColor: "text-[#6b38d4]", // primary purple
      trend: kpi.trend,
    },
    {
      title: "Kayıp Riski (Churn)",
      value: `${kpi.churnRatio}%`,
      icon: <UserMinus size={24} weight="duotone" />,
      iconColor: "text-[#EF4444]", // negative red
      trend: kpi.churnRatioTrend,
    },
    {
      title: "En Yoğun Kategori",
      value: kpi.topCategory.name,
      icon: <Shapes size={24} weight="duotone" />,
      iconColor: "text-[#F59E0B]", // amber
      subtitle: `Toplam geri bildirimin %${topCategoryPct}'i`,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {cards.map((card) => (
        <div
          key={card.title}
          className="bento-card relative overflow-hidden rounded-2xl p-6 flex flex-col justify-between border border-outline-variant/10 shadow-xs bg-white transition-all hover:shadow-md"
        >
          {/* Top Row: Icon & Title */}
          <div className="flex items-center gap-2.5 w-full mb-5">
            <div className={`flex items-center justify-center shrink-0 ${card.iconColor}`}>
              {card.icon}
            </div>
            <p className="text-sm font-bold text-on-surface-variant tracking-tight">
              {card.title}
            </p>
          </div>

          {/* Bottom Row: Value & Trend */}
          <div className="flex-1 w-full">
            {loading ? (
              <div className="shimmer-skeleton h-10 w-28 rounded-lg mt-1" />
            ) : (
              <>
                <h3 className="text-[32px] font-bold text-[#220053] tracking-tight leading-none mb-3">
                  {card.value}
                </h3>
                
                {/* Trend Info */}
                {card.trend && (
                  <div className="flex items-center gap-1.5">
                    {card.trend.isPositive ? (
                      <TrendUp size={16} weight="bold" className="text-positive" />
                    ) : (
                      <TrendDown size={16} weight="bold" className="text-negative" />
                    )}
                    <span className={`text-sm font-bold leading-none ${card.trend.isPositive ? "text-positive" : "text-negative"}`}>
                      {card.trend.value}
                    </span>
                    <span className="text-xs text-on-surface-variant font-medium opacity-80 leading-none mt-[1px]">
                      {card.trend.label}
                    </span>
                  </div>
                )}

                {/* Subtitle (e.g. category percentage) */}
                {card.subtitle && (
                  <p className="text-xs text-on-surface-variant font-medium mt-1.5 leading-none">
                    {card.subtitle}
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
