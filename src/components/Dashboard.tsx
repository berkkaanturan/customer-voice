"use client";

import { useState, useEffect, useCallback, useRef, Fragment } from "react";
import type { Review } from "@/lib/supabase";
import FilterBar from "./FilterBar";
import KpiCards from "./KpiCards";
import ReviewTable from "./ReviewTable";
import dynamic from "next/dynamic";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";

const SentimentPieChart = dynamic(() => import("./SentimentPieChart"), {
  ssr: false,
  loading: () => <div className="shimmer-skeleton h-48 w-48 rounded-full mx-auto" />,
});
const TrendLineChart = dynamic(() => import("./TrendLineChart"), {
  ssr: false,
  loading: () => <div className="shimmer-skeleton h-[260px] w-full rounded-xl" />,
});
const CategoryBarChart = dynamic(() => import("./CategoryBarChart"), {
  ssr: false,
  loading: () => <div className="shimmer-skeleton h-[350px] w-full rounded-xl" />,
});

export interface Filters {
  platform: string;
  sentiment: string;
  category: string;
  dateFrom: string;
  dateTo: string;
  search: string;
  sortBy: string;
  sortOrder: "asc" | "desc";
}

export interface KpiData {
  todayCount: number;
  totalCount: number;
  churnRatio: number;
  sentimentScore: number;
  topCategory: { name: string; count: number };
  trend?: {
    value: string;
    label: string;
    isPositive: boolean;
  };
  churnRatioTrend?: {
    value: string;
    label: string;
    isPositive: boolean;
  };
}

export interface SentimentDist {
  Positive: number;
  Negative: number;
}

export interface TrendPoint {
  date: string;
  label: string;
  total: number;
  positive: number;
  negative: number;
}

export interface CategoryDist {
  name: string;
  count: number;
}

export interface SmartInsight {
  total: number;
  positive: number;
  negative: number;
  topCategory: string;
}

interface ApiResponse {
  reviews: Review[];
  totalCount: number;
  kpi: KpiData;
  sentimentDistribution: SentimentDist;
  categoryDistribution: CategoryDist[];
  smartInsight: SmartInsight;
  dailyTrend: TrendPoint[];
}

export default function Dashboard() {
  const [globalFilters, setGlobalFilters] = useState({
    platform: "all",
    dateFrom: "",
    dateTo: "",
  });

  const [tableFilters, setTableFilters] = useState({
    category: "all",
    sentiment: "all",
    search: "",
    sortBy: "scraped_at",
    sortOrder: "desc" as "asc" | "desc",
  });

  const [activePreset, setActivePreset] = useState<string>("all");
  const statsCacheRef = useRef<Record<string, any>>({});

  const handlePresetChange = (preset: string) => {
    setActivePreset(preset);
    const today = new Date();
    const todayStr = today.toISOString().split("T")[0];
    
    if (preset === "all") {
      setPage(1);
      setGlobalFilters(prev => ({ ...prev, dateFrom: "", dateTo: "" }));
    } else {
      let fromDate = new Date();
      if (preset === "30d") {
        fromDate.setDate(today.getDate() - 30);
      } else if (preset === "60d") {
        fromDate.setDate(today.getDate() - 60);
      } else if (preset === "90d") {
        fromDate.setDate(today.getDate() - 90);
      } else if (preset === "1y") {
        fromDate.setFullYear(today.getFullYear() - 1);
      }
      const fromStr = fromDate.toISOString().split("T")[0];
      setPage(1);
      setGlobalFilters(prev => ({ ...prev, dateFrom: fromStr, dateTo: todayStr }));
    }
  };

  const [reviews, setReviews] = useState<Review[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [kpi, setKpi] = useState<KpiData>({
    todayCount: 0,
    totalCount: 0,
    churnRatio: 0,
    sentimentScore: 50,
    topCategory: { name: "-", count: 0 },
  });
  const [sentimentDist, setSentimentDist] = useState<SentimentDist>({
    Positive: 0,
    Negative: 0,
  });
  const [categoryDist, setCategoryDist] = useState<CategoryDist[]>([]);
  const [smartInsight, setSmartInsight] = useState<SmartInsight>({
    total: 0,
    positive: 0,
    negative: 0,
    topCategory: "-",
  });
  const [dailyTrend, setDailyTrend] = useState<TrendPoint[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(true);
  const [pageInput, setPageInput] = useState("1");
  const [editingPageIdx, setEditingPageIdx] = useState<number | null>(null);
  const limit = 20;

  // 1. Fetch Dashboard Stats (triggered ONLY on platform/date changes)
  const fetchDashboardData = useCallback(async () => {
    const cacheKey = `${globalFilters.platform}_${globalFilters.dateFrom}_${globalFilters.dateTo}`;
    if (statsCacheRef.current[cacheKey]) {
      const cached = statsCacheRef.current[cacheKey];
      setKpi(cached.kpi);
      setSentimentDist(cached.sentimentDist);
      setCategoryDist(cached.categoryDist);
      setSmartInsight(cached.smartInsight);
      setDailyTrend(cached.dailyTrend);
      return;
    }

    setLoading(true);
    try {
      const params = new URLSearchParams({
        platform: globalFilters.platform,
        sentiment: "all",
        category: "all",
        page: "1",
        limit: "1",
      });
      if (globalFilters.dateFrom) params.set("dateFrom", globalFilters.dateFrom);
      if (globalFilters.dateTo) params.set("dateTo", globalFilters.dateTo);

      const res = await fetch(`/api/reviews?${params.toString()}`);
      if (!res.ok) throw new Error("API error");
      const data: ApiResponse = await res.json();

      setKpi(data.kpi);
      setSentimentDist(data.sentimentDistribution);
      setCategoryDist(data.categoryDistribution || []);
      setSmartInsight(data.smartInsight);
      setDailyTrend(data.dailyTrend);

      statsCacheRef.current[cacheKey] = {
        kpi: data.kpi,
        sentimentDist: data.sentimentDistribution,
        categoryDist: data.categoryDistribution || [],
        smartInsight: data.smartInsight,
        dailyTrend: data.dailyTrend,
      };
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    } finally {
      setLoading(false);
    }
  }, [globalFilters]);

  // 2. Fetch Reviews Table (triggered on search, page, sorting, categories/sentiments)
  const fetchTableData = useCallback(async () => {
    setTableLoading(true);
    try {
      const params = new URLSearchParams({
        platform: globalFilters.platform,
        category: tableFilters.category,
        sentiment: tableFilters.sentiment,
        search: tableFilters.search,
        sortBy: tableFilters.sortBy,
        sortOrder: tableFilters.sortOrder,
        page: String(page),
        limit: String(limit),
        skipStats: "true",
      });
      if (globalFilters.dateFrom) params.set("dateFrom", globalFilters.dateFrom);
      if (globalFilters.dateTo) params.set("dateTo", globalFilters.dateTo);

      const res = await fetch(`/api/reviews?${params.toString()}`);
      if (!res.ok) throw new Error("API error");
      const data: ApiResponse = await res.json();

      setReviews(data.reviews);
      setTotalCount(data.totalCount);
    } catch (err) {
      console.error("Failed to fetch table data:", err);
    } finally {
      setTableLoading(false);
    }
  }, [globalFilters, tableFilters, page]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  useEffect(() => {
    fetchTableData();
  }, [fetchTableData]);

  useEffect(() => {
    setPageInput(String(page));
  }, [page]);

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

  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      let start = Math.max(2, page - 1);
      let end = Math.min(totalPages - 1, page + 1);
      
      if (page <= 2) {
        end = 4;
      } else if (page >= totalPages - 1) {
        start = totalPages - 3;
      }
      
      if (start > 2) {
        pages.push("...");
      }
      
      for (let i = start; i <= end; i++) {
        pages.push(i);
      }
      
      if (end < totalPages - 1) {
        pages.push("...");
      }
      
      pages.push(totalPages);
    }
    return pages;
  };

  // Smart insight text
  const insightText = (() => {
    const { total, positive, negative, topCategory } = smartInsight;
    if (total === 0) return "Son 24 saatte yeni yorum gelmedi.";
    return `Son 24 saatte toplam ${total} yorum geldi (${positive} pozitif, ${negative} negatif). En çok yorum gelen kategori: ${topCategory}.`;
  })();

  const dateRangeLabel = (() => {
    if (!globalFilters.dateFrom && !globalFilters.dateTo) {
      return "Oct 1 - Oct 31, 2023"; // Fallback placeholder matching design style
    }
    const formatDateShort = (dStr: string) => {
      const d = new Date(dStr);
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      return `${months[d.getMonth()]} ${d.getDate()}`;
    };
    const from = globalFilters.dateFrom ? formatDateShort(globalFilters.dateFrom) : "Start";
    const to = globalFilters.dateTo ? formatDateShort(globalFilters.dateTo) : "End";
    const year = new Date(globalFilters.dateTo || globalFilters.dateFrom || new Date()).getFullYear();
    return `${from} - ${to}, ${year}`;
  })();

  return (
    <div className="min-h-screen bg-background-alt text-on-surface" style={{ fontFamily: "Inter, sans-serif" }}>
      {/* ── TopNavBar ── */}
      <nav className="sticky top-0 z-50 flex items-center justify-between px-4 md:px-8 w-full h-16 bg-white border-b border-outline-variant/30 shadow-xs">
        <div className="flex flex-row items-center justify-between gap-3 md:gap-8 w-full md:w-auto">
          <div className="flex items-center shrink-0">
            <img src="/turknet_logo.png" className="h-5 md:h-6 w-auto shrink-0" alt="TurkNet Logo" />
            <span className="font-bold text-[#220053] text-lg md:text-xl tracking-tight flex items-center">
              <span className="text-[#220053] font-bold ml-4 md:ml-6 border-l-2 border-outline-variant/50 pl-4 md:pl-6 h-5 md:h-6 flex items-center select-none">VoC Hub</span>
            </span>
          </div>
          <div className="md:w-auto shrink-0">
            <FilterBar platform={globalFilters.platform} onChange={(plat) => {
              setPage(1);
              setGlobalFilters(prev => ({ ...prev, platform: plat }));
            }} />
          </div>
        </div>
      </nav>

      <main className="p-4 md:p-8 max-w-[1600px] mx-auto space-y-4 md:space-y-6">
        {/* Header */}
        <div className="flex flex-col lg:flex-row justify-between lg:items-center gap-4 bg-white p-4 md:p-6 rounded-2xl border border-outline-variant/10 shadow-xs">
          <div className="flex items-center">
            <h1 className="text-2xl md:text-[28px] font-bold text-[#220053] tracking-tight leading-none">Voice of Customer Genel Bakış</h1>
          </div>

          {/* Date Selector Controls */}
          <div className="flex flex-col md:flex-row flex-wrap items-stretch md:items-center gap-3 w-full lg:w-auto">
            {/* Active Range Button */}
            <div className="flex items-center justify-center md:justify-start gap-2 px-4 py-2 bg-white border border-outline-variant rounded-xl text-xs font-bold text-on-surface select-none">
              <span className="material-symbols-outlined text-[18px]">calendar_month</span>
              <span>{activePreset === "all" ? "Tüm Zamanlar" : activePreset === "30d" ? "Son 30 Gün" : activePreset === "60d" ? "Son 60 Gün" : activePreset === "90d" ? "Son 90 Gün" : activePreset === "1y" ? "Son 1 Yıl" : "Özel Aralık"}</span>
            </div>

            {/* Quick Presets */}
            <div className="flex overflow-x-auto items-center bg-surface-container-low p-1 rounded-lg border border-outline-variant/10 [&::-webkit-scrollbar]:hidden">
              {[
                { label: "30 Gün", value: "30d" },
                { label: "60 Gün", value: "60d" },
                { label: "90 Gün", value: "90d" },
                { label: "1 Yıl", value: "1y" },
                { label: "Tümü", value: "all" }
              ].map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => handlePresetChange(preset.value)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer whitespace-nowrap ${
                    activePreset === preset.value
                      ? "bg-white text-secondary shadow-xs"
                      : "text-on-surface-variant hover:text-primary"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Custom Range Inputs */}
            <div className="flex items-center justify-between md:justify-start gap-2 w-full md:w-auto">
              <input
                type="date"
                value={globalFilters.dateFrom}
                onChange={(e) => {
                  setActivePreset("custom");
                  setPage(1);
                  setGlobalFilters(prev => ({ ...prev, dateFrom: e.target.value }));
                }}
                className="flex-1 md:flex-none bg-white border border-outline-variant text-xs px-2 py-1.5 rounded-lg text-on-surface font-semibold focus:outline-none focus:ring-2 focus:ring-secondary/20 cursor-pointer min-w-0"
              />
              <span className="text-xs text-on-surface-variant font-medium shrink-0">ve</span>
              <input
                type="date"
                value={globalFilters.dateTo}
                onChange={(e) => {
                  setActivePreset("custom");
                  setPage(1);
                  setGlobalFilters(prev => ({ ...prev, dateTo: e.target.value }));
                }}
                className="flex-1 md:flex-none bg-white border border-outline-variant text-xs px-2 py-1.5 rounded-lg text-on-surface font-semibold focus:outline-none focus:ring-2 focus:ring-secondary/20 cursor-pointer min-w-0"
              />
            </div>
          </div>
        </div>

        {/* Smart Insight Banner */}
        {loading ? (
          <div className="shimmer-skeleton h-[54px] w-full rounded-xl" />
        ) : (
          <div className="bento-card rounded-xl px-6 py-4 flex items-center gap-3 border-l-4 border-l-secondary bg-white">
            <span className="material-symbols-outlined text-secondary text-2xl select-none">insights</span>
            <p className="text-sm text-on-surface font-medium">{insightText}</p>
          </div>
        )}

        {/* KPI Row */}
        <KpiCards kpi={kpi} loading={loading} />

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Sentiment Distribution */}
          <div className="bento-card rounded-xl p-6 lg:col-span-1 flex flex-col h-[450px]">
            <div className="flex items-center justify-between mb-6">
              <h4 className="text-base font-semibold">Duygu Dağılımı</h4>
            </div>
            <div className="flex-1 flex flex-col items-center justify-center">
              {loading ? (
                <div className="shimmer-skeleton h-48 w-48 rounded-full" />
              ) : (
                <SentimentPieChart data={sentimentDist} />
              )}
            </div>
          </div>

          {/* Category Bar Chart */}
          <div className="bento-card rounded-2xl p-6 lg:col-span-2 flex flex-col h-[450px]">
            <div className="flex items-center justify-between mb-6 border-b border-outline-variant/10 pb-3">
              <h4 className="text-base font-bold text-[#220053]">Kategoriye Göre Yorumlar</h4>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-4">
              {loading ? (
                <div className="space-y-4">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="shimmer-skeleton h-8 w-full rounded-lg" />
                  ))}
                </div>
              ) : (
                <CategoryBarChart data={categoryDist} />
              )}
            </div>
          </div>
        </div>

        {/* Trend Chart */}
        <div className="bento-card rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-base font-semibold">Günlük Yorum Hacim Trendi</h4>
          </div>
          {loading ? (
            <div className="shimmer-skeleton h-[260px] w-full rounded-xl" />
          ) : (
            <TrendLineChart key={dailyTrend.map((d) => d.date).join(",")} data={dailyTrend} />
          )}
        </div>

        {/* Review Table */}
        <div className="bento-card rounded-2xl overflow-hidden shadow-xs border border-outline-variant/10 bg-white">
          <ReviewTable
            reviews={reviews}
            loading={tableLoading}
            onMarkRead={handleMarkRead}
            totalCount={totalCount}
            todayCount={kpi.todayCount}
            filters={tableFilters}
            onFilterChange={(newFilters) => {
              setPage(1);
              setTableFilters(newFilters);
            }}
          />

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="px-6 py-4 border-t border-outline-variant flex items-center justify-between">
              <span className="text-xs text-on-surface-variant font-medium">
                {totalCount.toLocaleString("tr-TR")} yorum arasından {Math.min(reviews.length, limit)} tanesi gösteriliyor
              </span>
              <div className="flex items-center gap-4">
                <div className="flex gap-1.5 select-none">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="border border-outline-variant rounded-lg hover:bg-surface-container transition-all disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed flex items-center justify-center min-w-[32px] h-[32px]"
                  >
                    <CaretLeft size={12} weight="bold" />
                  </button>
                  {getPageNumbers().map((p, idx) => (
                    <Fragment key={idx}>
                      {p === "..." && editingPageIdx === idx ? (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            const parsed = parseInt(pageInput, 10);
                            if (!isNaN(parsed) && parsed >= 1 && parsed <= totalPages) {
                              setPage(parsed);
                            }
                            setEditingPageIdx(null);
                          }}
                        >
                          <input
                            autoFocus
                            type="number"
                            min={1}
                            max={totalPages}
                            value={pageInput}
                            onChange={(e) => setPageInput(e.target.value)}
                            onBlur={() => setEditingPageIdx(null)}
                            className="w-[42px] h-[32px] text-xs font-bold text-center border border-primary rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30 text-on-surface hide-spin-button"
                            placeholder="..."
                          />
                        </form>
                      ) : (
                        <button
                          onClick={() => {
                            if (typeof p === "number") {
                              setPage(p);
                            } else {
                              setEditingPageIdx(idx);
                              setPageInput("");
                            }
                          }}
                          className={`text-xs font-bold rounded-lg transition-all min-w-[32px] h-[32px] flex items-center justify-center ${
                            p === page
                              ? "bg-[#6b38d4] text-white shadow-xs"
                              : p === "..."
                              ? "text-on-surface-variant/70 hover:text-on-surface hover:bg-surface-container cursor-pointer"
                              : "border border-outline-variant hover:bg-surface-container cursor-pointer text-on-surface-variant"
                          }`}
                        >
                          {p}
                        </button>
                      )}
                    </Fragment>
                  ))}
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="border border-outline-variant rounded-lg hover:bg-surface-container transition-all disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed flex items-center justify-center min-w-[32px] h-[32px]"
                  >
                    <CaretRight size={12} weight="bold" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="mt-12 py-8 px-8 text-center border-t border-outline-variant">
        <p className="text-on-surface-variant text-xs">© 2026 TurkNet VoC Hub.</p>
      </footer>
    </div>
  );
}
