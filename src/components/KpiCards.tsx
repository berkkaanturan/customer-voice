"use client";

import type { KpiData } from "./Dashboard";
import { ChatCircleText, TrendDown, Warning, Database, Clock } from "@phosphor-icons/react";

// Extend the interface to include totalCount
interface ExtendedKpiData extends KpiData {
  totalCount: number;
}

interface KpiCardsProps {
  kpi: ExtendedKpiData;
  loading: boolean;
}

export default function KpiCards({ kpi, loading }: KpiCardsProps) {
  const cards = [
    {
      title: "Filtrelenmiş Toplam Yorum",
      value: kpi.totalCount,
      suffix: " adet",
      icon: <Database size={24} weight="regular" className="text-brand-accent" />,
      color: "text-brand-primary",
      isText: false,
    },
    {
      title: "Bugün Gelen Yorum",
      value: kpi.todayCount,
      suffix: " adet",
      icon: <Clock size={24} weight="regular" className="text-brand-accent" />,
      color: "text-brand-primary",
      isText: false,
    },
    {
      title: "Negatif Yorum Oranı",
      value: kpi.negativeRatio,
      suffix: "%",
      icon: <TrendDown size={24} weight="regular" className={kpi.negativeRatio > 35 ? "text-sentiment-neg" : "text-sentiment-pos"} />,
      color: kpi.negativeRatio > 40
        ? "text-sentiment-neg"
        : kpi.negativeRatio > 25
          ? "text-sentiment-neut"
          : "text-sentiment-pos",
      isText: false,
    },
    {
      title: "En Çok Şikayet Edilen Konu",
      value: kpi.topCategory.name,
      suffix: kpi.topCategory.count > 0 ? ` (${kpi.topCategory.count})` : "",
      icon: <Warning size={24} weight="regular" className="text-sentiment-neut" />,
      color: "text-brand-primary",
      isText: true,
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
      {cards.map((card) => (
        <div key={card.title} className="flex flex-col gap-3">
          {/* Card Container */}
          <div className="bento-card p-6 flex items-center justify-between min-h-[95px]">
            <div className="space-y-1 pr-2 overflow-hidden">
              {loading ? (
                <div className="shimmer-skeleton h-8 w-20 rounded-lg" />
              ) : (
                <div className="flex items-baseline overflow-hidden">
                  {card.isText ? (
                    <p className={`text-sm font-bold ${card.color} tracking-tight font-sans truncate`} title={String(card.value)}>
                      {card.value}
                      <span className="text-[10px] font-normal text-text-muted ml-1">
                        {card.suffix}
                      </span>
                    </p>
                  ) : (
                    <p className={`text-2xl font-semibold ${card.color} tracking-tight font-mono`}>
                      {card.value}
                      <span className="text-xs font-medium text-text-muted ml-0.5 font-sans">
                        {card.suffix}
                      </span>
                    </p>
                  )}
                </div>
              )}
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center flex-shrink-0">
              {card.icon}
            </div>
          </div>
          {/* Label outside and below the card */}
          <div className="px-4">
            <h3 className="text-[10px] font-semibold text-text-muted tracking-wider uppercase truncate">
              {card.title}
            </h3>
          </div>
        </div>
      ))}
    </div>
  );
}
