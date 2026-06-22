"use client";

import { useState, useEffect, useCallback } from "react";
import type { Review } from "@/lib/supabase";
import FilterBar from "./FilterBar";
import KpiCards from "./KpiCards";
import ReviewTable from "./ReviewTable";
import dynamic from "next/dynamic";
import { motion, type Variants } from "framer-motion";
import { CaretLeft, CaretRight, ChartBar } from "@phosphor-icons/react";

// Recharts must be loaded client-side only (uses DOM/window)
const SentimentPieChart = dynamic(() => import("./SentimentPieChart"), {
  ssr: false,
  loading: () => <div className="shimmer-skeleton h-[260px] w-full rounded-2xl" />,
});
const TrendLineChart = dynamic(() => import("./TrendLineChart"), {
  ssr: false,
  loading: () => <div className="shimmer-skeleton h-[260px] w-full rounded-2xl" />,
});

export interface Filters {
  platform: string;
  sentiment: string;
  category: string;
  dateFrom: string;
  dateTo: string;
}

export interface KpiData {
  todayCount: number;
  totalCount: number;
  negativeRatio: number;
  topCategory: { name: string; count: number };
}

export interface SentimentDist {
  Positive: number;
  Negative: number;
  Neutral: number;
}

export interface TrendPoint {
  date: string;
  total: number;
  positive: number;
  negative: number;
  neutral: number;
}

interface ApiResponse {
  reviews: Review[];
  totalCount: number;
  kpi: KpiData;
  sentimentDistribution: SentimentDist;
  dailyTrend: TrendPoint[];
}

// Stagger animation definitions
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
};

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 15 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      type: "spring",
      stiffness: 80,
      damping: 18,
    },
  },
};

export default function Dashboard() {
  const [filters, setFilters] = useState<Filters>({
    platform: "all",
    sentiment: "all",
    category: "all",
    dateFrom: "",
    dateTo: "",
  });
  const [reviews, setReviews] = useState<Review[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [kpi, setKpi] = useState<KpiData>({
    todayCount: 0,
    totalCount: 0,
    negativeRatio: 0,
    topCategory: { name: "-", count: 0 },
  });
  const [sentimentDist, setSentimentDist] = useState<SentimentDist>({
    Positive: 0,
    Negative: 0,
    Neutral: 0,
  });
  const [dailyTrend, setDailyTrend] = useState<TrendPoint[]>([]);
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [loading, setLoading] = useState(true);
  const limit = 20;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        platform: filters.platform,
        sentiment: filters.sentiment,
        category: filters.category,
        page: String(page),
        limit: String(limit),
      });
      if (filters.dateFrom) params.set("dateFrom", filters.dateFrom);
      if (filters.dateTo) params.set("dateTo", filters.dateTo);

      const res = await fetch(`/api/reviews?${params.toString()}`);
      if (!res.ok) throw new Error("API error");
      const data: ApiResponse = await res.json();

      setReviews(data.reviews);
      setTotalCount(data.totalCount);
      setKpi(data.kpi);
      setSentimentDist(data.sentimentDistribution);
      setDailyTrend(data.dailyTrend);
    } catch (err) {
      console.error("Failed to fetch data:", err);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Sync page input when page changes
  useEffect(() => {
    setPageInput(String(page));
  }, [page]);

  const handleFilterChange = (newFilters: Filters) => {
    setPage(1);
    setFilters(newFilters);
  };

  const handleMarkRead = async (id: string) => {
    try {
      await fetch("/api/reviews", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      setReviews((prev) =>
        prev.map((r) => (r.id === id ? { ...r, is_read: true } : r))
      );
    } catch (err) {
      console.error("Failed to mark as read:", err);
    }
  };

  const totalPages = Math.ceil(totalCount / limit);

  return (
    <div className="min-h-screen flex flex-col bg-bg-main">
      {/* ── Asymmetric Left-Aligned Header ── */}
      <header className="bg-white border-b border-slate-200/50 py-10">
        <div className="max-w-[1400px] mx-auto px-8 md:px-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5 text-brand-accent">
              <ChartBar size={28} weight="bold" />
              <span className="text-[10px] font-bold tracking-widest uppercase">Müşteri Deneyimi Analiz Paneli</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tighter text-brand-primary leading-none">
              Müşteri Sesi
            </h1>
            <p className="text-xs text-text-muted max-w-[65ch] leading-relaxed">
              Google Play Store, Apple App Store, Şikayetvar ve Ekşi Sözlük kanallarından anlık olarak derlenen gerçek kullanıcı yorumları ve sınıflandırılmış arıza bildirimleri.
            </p>
          </div>
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/60 rounded-2xl py-2 px-3.5 self-start md:self-auto shadow-sm">
            <span className="w-2.5 h-2.5 rounded-full bg-sentiment-pos animate-pulse" />
            <span className="text-[10px] font-bold text-brand-primary uppercase tracking-wider">Canlı Veri Senkronizasyonu</span>
          </div>
        </div>
      </header>

      {/* ── Main Content Area ── */}
      <main className="flex-1 max-w-[1400px] w-full mx-auto px-8 md:px-12 py-10">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="space-y-10"
        >
          {/* Row 1: Filters */}
          <motion.div variants={cardVariants}>
            <FilterBar filters={filters} onChange={handleFilterChange} />
          </motion.div>

          {/* Row 2: KPI Metrics */}
          <motion.div variants={cardVariants}>
            <KpiCards kpi={kpi} loading={loading} />
          </motion.div>

          {/* Row 3: Charts (Asymmetric Layout 3/2 split) */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
            {/* Trend Line Chart (60%) */}
            <motion.div variants={cardVariants} className="lg:col-span-3 flex flex-col gap-3">
              <div className="bento-card p-8 flex flex-col justify-between min-h-[330px]">
                {loading ? (
                  <div className="shimmer-skeleton h-[260px] w-full rounded-2xl" />
                ) : (
                  <TrendLineChart key={dailyTrend.map((d) => d.date).join(",")} data={dailyTrend} />
                )}
              </div>
              <div className="px-6">
                <h3 className="text-[10px] font-semibold text-text-muted tracking-wider uppercase">
                  Günlük Yorum Hacim Trendi
                </h3>
                <p className="text-[11px] text-text-light mt-0.5">
                  Platformlar bazında seçili tarih aralığında biriken toplam ve duygu dağılım eğrisi.
                </p>
              </div>
            </motion.div>

            {/* Sentiment Pie Chart (40%) */}
            <motion.div variants={cardVariants} className="lg:col-span-2 flex flex-col gap-3">
              <div className="bento-card p-8 flex flex-col justify-between min-h-[330px]">
                {loading ? (
                  <div className="shimmer-skeleton h-[260px] w-full rounded-2xl" />
                ) : (
                  <SentimentPieChart data={sentimentDist} />
                )}
              </div>
              <div className="px-6">
                <h3 className="text-[10px] font-semibold text-text-muted tracking-wider uppercase">
                  Kümülatif Duygu Dağılımı
                </h3>
                <p className="text-[11px] text-text-light mt-0.5">
                  Filtrelenmiş yorumların oransal olarak duygu (pozitif, negatif, nötr) analizi.
                </p>
              </div>
            </motion.div>
          </div>

          {/* Row 4: Review Table */}
          <motion.div variants={cardVariants} className="flex flex-col gap-3">
            <div className="bento-card overflow-hidden">
              <ReviewTable
                reviews={reviews}
                loading={loading}
                onMarkRead={handleMarkRead}
              />
              
              {/* Pagination */}
              {totalPages > 1 && (
                <div className="px-8 py-5 border-t border-slate-100 flex items-center justify-between bg-slate-50/30">
                  <p className="text-xs text-text-muted font-mono">
                    Sayfa {page} / {totalPages}
                  </p>
                  
                  <div className="flex items-center gap-6">
                    {/* Direct Page Input */}
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-text-muted font-semibold uppercase tracking-wider">Sayfaya Git:</span>
                      <input
                        type="number"
                        min={1}
                        max={totalPages}
                        value={pageInput}
                        onChange={(e) => setPageInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            const val = parseInt(pageInput, 10);
                            if (val >= 1 && val <= totalPages) {
                              setPage(val);
                            } else {
                              setPageInput(String(page));
                            }
                          }
                        }}
                        onBlur={() => {
                          const val = parseInt(pageInput, 10);
                          if (val >= 1 && val <= totalPages) {
                            setPage(val);
                          } else {
                            setPageInput(String(page));
                          }
                        }}
                        className="w-14 bg-white border border-slate-200 text-center py-1 text-xs rounded-xl focus:outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-accent/10 font-mono font-semibold text-brand-primary"
                      />
                    </div>

                    {/* Navigation Buttons */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page <= 1}
                        className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-2xl border border-slate-200 bg-white text-text-muted hover:bg-slate-50 disabled:opacity-30 disabled:hover:bg-white transition-all cursor-pointer disabled:cursor-not-allowed"
                      >
                        <CaretLeft size={14} weight="bold" />
                        Önceki
                      </button>
                      <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page >= totalPages}
                        className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-2xl border border-slate-200 bg-white text-text-muted hover:bg-slate-50 disabled:opacity-30 disabled:hover:bg-white transition-all cursor-pointer disabled:cursor-not-allowed"
                      >
                        Sonraki
                        <CaretRight size={14} weight="bold" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 flex items-center justify-between">
              <div>
                <h3 className="text-[10px] font-semibold text-text-muted tracking-wider uppercase">
                  Müşteri Yorum Ayrıntıları
                </h3>
                <p className="text-[11px] text-text-light mt-0.5">
                  Çekilmiş olan tüm verilerin detaylı listesi. Yorumun üzerine tıklayarak genişletebilirsiniz.
                </p>
              </div>
              <span className="text-[10px] font-mono font-bold bg-white text-brand-accent py-1 px-3 rounded-xl border border-slate-200/80 shadow-sm">
                Toplam {totalCount} Geri Bildirim
              </span>
            </div>
          </motion.div>
        </motion.div>
      </main>

      {/* ── Footer ── */}
      <footer className="bg-white border-t border-slate-200/50 mt-auto py-6">
        <div className="max-w-[1400px] mx-auto px-8 md:px-12 text-center text-[10px] font-semibold text-text-light tracking-wider uppercase">
          Müşteri Deneyimi Analiz Platformu — Supabase & Rule-Based NLP Pipeline
        </div>
      </footer>
    </div>
  );
}
