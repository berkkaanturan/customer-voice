"use client";

import type { KpiData } from "./Dashboard";

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
      title: "Toplam Yorum",
      value: kpi.totalCount.toLocaleString("tr-TR"),
      icon: "chat",
      iconBg: "bg-[#e8f0fe]",
      iconColor: "text-blue-600",
      trend: kpi.trend,
    },
    {
      title: "Kayıp Riski (Churn Risk) Oranı",
      value: `${kpi.churnRatio}%`,
      icon: "trending_down",
      iconBg: "bg-[#fde8e8]",
      iconColor: "text-negative",
      trend: kpi.churnRatioTrend,
    },
    {
      title: "En Sık Yorum Gelen Kategori",
      value: kpi.topCategory.name,
      icon: "warning",
      iconBg: "bg-[#fef3c7]",
      iconColor: "text-amber-600",
      subtitle: `toplam şikayetin %${topCategoryPct}'i`,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {cards.map((card) => (
        <div
          key={card.title}
          className="bento-card rounded-2xl p-6 flex items-start gap-4 border border-outline-variant/10 shadow-xs bg-white"
        >
          {/* Icon Container */}
          <div className={`${card.iconBg} ${card.iconColor} w-12 h-12 rounded-xl flex items-center justify-center shrink-0`}>
            <span className="material-symbols-outlined text-[24px] select-none">{card.icon}</span>
          </div>

          {/* Card Content */}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-on-surface-variant tracking-tight uppercase opacity-85">
              {card.title}
            </p>
            {loading ? (
              <div className="shimmer-skeleton h-8 w-24 rounded-lg mt-2" />
            ) : (
              <>
                <h3 className="text-[28px] font-bold mt-1 text-[#220053] tracking-tight leading-none">
                  {card.value}
                </h3>
                
                {/* Trend Info */}
                {card.trend && (
                  <div className="flex items-center gap-1 mt-2">
                    <span className="material-symbols-outlined text-xs font-bold leading-none align-middle select-none">
                      {card.trend.isPositive ? "trending_up" : "trending_down"}
                    </span>
                    <span className={`text-xs font-bold leading-none ${card.trend.isPositive ? "text-positive" : "text-negative"}`}>
                      {card.trend.value}
                    </span>
                    <span className="text-xs text-on-surface-variant font-medium opacity-80 leading-none">
                      {card.trend.label}
                    </span>
                  </div>
                )}

                {/* Subtitle (e.g. category percentage) */}
                {card.subtitle && (
                  <p className="text-xs text-on-surface-variant font-medium mt-2 leading-none">
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
