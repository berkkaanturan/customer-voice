"use client";

import { useState, Fragment, useCallback, useEffect } from "react";
import type { Review } from "@/lib/supabase";
import {
  GooglePlayLogo,
  Megaphone,
  Quotes,
  LinkSimpleHorizontal,
  Tray,
  Clock,
  User,
  CaretDown,
  CaretUp,
  SortAscending,
} from "@phosphor-icons/react";

// ── Churn Risk Keywords ──
const CHURN_KEYWORDS = [
  "iptal", "tüketici hakem heyeti", "avukat", "mahkeme", "taahhüt",
  "cayma", "dava", "savcılık", "btk", "şikayet ettim", "hukuki",
  "ceza", "sözleşme feshi", "ihtarname",
];

function hasChurnRisk(text: string): boolean {
  const lower = text.toLowerCase();
  return CHURN_KEYWORDS.some((kw) => lower.includes(kw));
}

const CATEGORIES = [
  "Abonelik", "Adres Değişikliği", "ADSL", "Altyapı", "Altyapısız İnternet", "Arıza",
  "Bakım Çalışması", "Dondurma İşlemi", "Ev Telefonu Hizmeti", "Evde İnternet", "Fatura",
  "Fiber İnternet", "Gezgin İnternet", "Gigafiber", "Hız Testi", "İnternet Kesintisi",
  "İnternet Paketleri", "Modem", "Online İşlemler", "Ping Sorunu", "VDSL", "Yalın İnternet", "Genel"
].sort((a, b) => a.localeCompare(b, "tr"));

// ── Platform Badges ──
const PLATFORM_BADGE: Record<string, { bg: string; text: string }> = {
  "Play Store": { bg: "bg-emerald-100", text: "text-emerald-700" },
  "App Store": { bg: "bg-blue-100", text: "text-blue-700" },
  "Şikayetvar": { bg: "bg-blue-100", text: "text-blue-700" },
  "Ekşi Sözlük": { bg: "bg-orange-100", text: "text-orange-700" },
};

const AppStoreIcon = () => (
  <svg width="14" height="14" viewBox="0 0 640 640" className="text-blue-600 inline-block align-middle fill-current shrink-0">
    <path d="m319.9 184.9l9.1-15.7c5.6-9.8 18.1-13.1 27.9-7.5s13.1 18.1 7.5 27.9l-87.5 151.5h63.3c20.5 0 32 24.1 23.1 40.8H177.8c-11.3 0-20.4-9.1-20.4-20.4s9.1-20.4 20.4-20.4h52l66.6-115.4l-20.8-36.1c-5.6-9.8-2.3-22.2 7.5-27.9c9.8-5.6 22.2-2.3 27.9 7.5zm-78.7 218l-19.6 34c-5.6 9.8-18.1 13.1-27.9 7.5s-13.1-18.1-7.5-27.9l14.6-25.2c16.4-5.1 29.8-1.2 40.4 11.6m168.9-61.7h53.1c11.3 0 20.4 9.1 20.4 20.4s-9.1 20.4-20.4 20.4h-29.5l19.9 34.5c5.6 9.8 2.3 22.2-7.5 27.9c-9.8 5.6-22.2 2.3-27.9-7.5c-33.5-58.1-58.7-101.6-75.4-130.6c-17.1-29.5-4.9-59.1 7.2-69.1c13.4 23 33.4 57.7 60.1 104M320 72C183 72 72 183 72 320s111 248 248 248s248-111 248-248S457 72 320 72M104 320c0-119.3 96.7-216 216-216s216 96.7 216 216s-96.7 216-216 216s-216-96.7-216-216" />
  </svg>
);

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  "Play Store": <GooglePlayLogo size={14} weight="regular" className="text-emerald-600" />,
  "App Store": <AppStoreIcon />,
  "Şikayetvar": <Megaphone size={14} weight="regular" className="text-blue-600" />,
  "Ekşi Sözlük": <Quotes size={14} weight="regular" className="text-orange-600" />,
};

const SENTIMENT_BADGE: Record<string, { class: string; label: string }> = {
  Positive: { class: "bg-[#e6f4ea] text-[#137333]", label: "Pozitif" },
  Negative: { class: "bg-[#fde8e8] text-[#c53030]", label: "Negatif" },
  Neutral: { class: "bg-slate-100 text-slate-700", label: "Nötr" },
};

type SortField = "scraped_at" | "category" | "sentiment";

interface ReviewTableProps {
  reviews: Review[];
  loading: boolean;
  onMarkRead: (id: string) => void;
  totalCount: number;
  todayCount: number;
  filters: any;
  onFilterChange: (filters: any) => void;
}

// ── Highlight helper ──
function highlightText(text: string, query: string): React.ReactNode {
  if (!query || query.length < 2) return text;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(regex);
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="bg-yellow-200 rounded-sm px-0.5">{part}</mark>
    ) : (
      part
    )
  );
}

export default function ReviewTable({
  reviews,
  loading,
  onMarkRead,
  totalCount,
  todayCount,
  filters,
  onFilterChange
}: ReviewTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState(filters.search || "");
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    setSearchQuery(filters.search || "");
  }, [filters.search]);

  useEffect(() => {
    const handler = setTimeout(() => {
      if (searchQuery !== filters.search) {
        onFilterChange({ ...filters, search: searchQuery });
      }
    }, 500);
    return () => clearTimeout(handler);
  }, [searchQuery, onFilterChange, filters]);

  const toggleExpand = (review: Review) => {
    setExpandedId((prev) => (prev === review.id ? null : review.id));
    if (!review.is_read) onMarkRead(review.id);
  };

  const handleSort = (field: SortField) => {
    let nextOrder: "asc" | "desc" = "desc";
    if (filters.sortBy === field) {
      nextOrder = filters.sortOrder === "desc" ? "asc" : "desc";
    } else {
      nextOrder = field === "scraped_at" ? "desc" : "asc";
    }
    onFilterChange({ ...filters, sortBy: field, sortOrder: nextOrder });
  };

  // Export CSV
  const handleExport = useCallback(() => {
    const headers = ["Platform", "Tarih", "Yorum", "Kategori", "Duygu", "Yazar", "Kaynak URL"];
    const rows = reviews.map((r) => [
      r.platform_name,
      new Date(r.scraped_at).toLocaleDateString("tr-TR"),
      `"${r.original_text.replace(/"/g, '""')}"`,
      r.category,
      r.sentiment === "Positive" ? "Pozitif" : "Negatif",
      r.author || "Anonim",
      r.source_url || "",
    ]);
    const csv = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");
    const BOM = "\uFEFF";
    const blob = new Blob([BOM + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `voc-yorumlar-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [reviews]);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const day = String(d.getDate()).padStart(2, "0");
    const months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
    const month = months[d.getMonth()];
    const year = d.getFullYear();
    return `${day} ${month}, ${year}`;
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (filters.sortBy !== field) return <SortAscending size={12} className="text-on-surface-variant/40 ml-1" />;
    if (filters.sortOrder === "asc") return <CaretUp size={12} className="text-secondary ml-1" />;
    return <CaretDown size={12} className="text-secondary ml-1" />;
  };



  return (
    <>
      {/* Table Header Bar */}
      <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <h4 className="text-base font-bold text-[#220053]">Son Gelen Yorumlar</h4>
          <div className="bg-[#e6f4ea] text-[#137333] px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1.5 border border-emerald-200/40">
            <span className="w-1.5 h-1.5 rounded-full bg-[#137333] animate-pulse" />
            Bugün Gelen: {todayCount} Yeni Yorum
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-base select-none">search</span>
            <input
              className="pl-9 pr-4 py-1.5 border border-outline-variant rounded-full text-xs bg-white text-on-surface focus:ring-secondary outline-none w-60 focus:ring-2 focus:ring-secondary/20 transition-all font-medium"
              placeholder="Yorumlarda ara..."
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          {/* Filter button */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1 text-xs font-semibold px-3 py-1.5 border rounded-lg transition-all cursor-pointer ${
              showFilters
                ? "bg-[#6b38d4]/10 border-[#6b38d4] text-[#6b38d4]"
                : "border-outline-variant text-on-surface-variant hover:bg-slate-50"
            }`}
          >
            <span className="material-symbols-outlined text-[16px] select-none">tune</span>
            Filtre
          </button>
          {/* Export */}
          <button
            onClick={handleExport}
            className="bg-[#6b38d4] text-on-secondary px-4 py-1.5 rounded-lg text-xs font-bold hover:opacity-90 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px] select-none">download</span>
            Dışa Aktar
          </button>
        </div>
      </div>

      {/* Collapsible Dropdown Filters */}
      {showFilters && (
        <div className="px-6 py-4 bg-surface-container-low border-b border-outline-variant/50 flex gap-6 items-center flex-wrap">
          {/* Category Dropdown */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Kategori Seçin</label>
            <select
              value={filters.category}
              onChange={(e) => onFilterChange({ ...filters, category: e.target.value })}
              className="bg-white border border-outline-variant text-xs px-3 py-1.5 rounded-lg text-on-surface font-semibold focus:outline-none focus:ring-2 focus:ring-secondary/20 cursor-pointer"
            >
              <option value="all">Tümü (Tüm Kategoriler)</option>
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>

          {/* Sentiment Dropdown */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Duygu Seçin</label>
            <select
              value={filters.sentiment}
              onChange={(e) => onFilterChange({ ...filters, sentiment: e.target.value })}
              className="bg-white border border-outline-variant text-xs px-3 py-1.5 rounded-lg text-on-surface font-semibold focus:outline-none focus:ring-2 focus:ring-secondary/20 cursor-pointer"
            >
              <option value="all">Tümü (Tüm Duygular)</option>
              <option value="Positive">Pozitif</option>
              <option value="Negative">Negatif</option>
            </select>
          </div>

          {/* Clear Filters Button */}
          {(filters.category !== "all" || filters.sentiment !== "all") && (
            <button
              onClick={() => onFilterChange({ ...filters, category: "all", sentiment: "all" })}
              className="mt-4 text-xs text-[#6b38d4] font-bold hover:text-primary transition-colors cursor-pointer flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[16px]">clear</span>
              Filtreleri Temizle
            </button>
          )}
        </div>
      )}

      {/* Table Content */}
      {loading ? (
        <div className="p-8 space-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="shimmer-skeleton h-14 w-full rounded-lg" />
          ))}
        </div>
      ) : reviews.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-on-surface-variant">
          <Tray size={48} weight="light" className="mb-4 opacity-40" />
          <p className="text-sm font-semibold">Sonuç bulunamadı</p>
          <p className="text-xs mt-1">Filtrelerinizi veya aramanızı değiştirin</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="premium-table">
            <thead>
              <tr className="bg-surface-container-lowest border-b border-outline-variant">
                <th className="px-6 py-4 uppercase tracking-wider text-xs font-bold text-on-surface-variant/80">Platform</th>
                <th
                  className="px-4 py-4 uppercase tracking-wider text-xs font-bold text-on-surface-variant/80 cursor-pointer select-none hover:text-primary transition-colors"
                  onClick={() => handleSort("scraped_at")}
                >
                  <span className="inline-flex items-center">TARİH <SortIcon field="scraped_at" /></span>
                </th>
                <th className="px-4 py-4 uppercase tracking-wider text-xs font-bold text-on-surface-variant/80 w-1/2">YORUM METNİ</th>
                <th
                  className="px-4 py-4 uppercase tracking-wider text-xs font-bold text-on-surface-variant/80 cursor-pointer select-none hover:text-primary transition-colors"
                  onClick={() => handleSort("category")}
                >
                  <span className="inline-flex items-center">KATEGORİ <SortIcon field="category" /></span>
                </th>
                <th
                  className="px-6 py-4 uppercase tracking-wider text-xs font-bold text-on-surface-variant/80 cursor-pointer select-none hover:text-primary transition-colors"
                  onClick={() => handleSort("sentiment")}
                >
                  <span className="inline-flex items-center">DUYGU <SortIcon field="sentiment" /></span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {reviews.map((review) => {
                const isExpanded = expandedId === review.id;
                const sentiment = SENTIMENT_BADGE[review.sentiment] || SENTIMENT_BADGE.Negative;
                const badge = PLATFORM_BADGE[review.platform_name] || { bg: "bg-gray-200", text: "text-gray-700" };
                const isChurn = hasChurnRisk(review.original_text);

                return (
                  <Fragment key={review.id}>
                    <tr
                      className="hover:bg-surface-container-low transition-colors cursor-pointer"
                      onClick={() => toggleExpand(review)}
                    >
                      {/* Platform */}
                      <td className="px-6 py-4">
                        <span className="flex items-center gap-1.5">
                          {PLATFORM_ICONS[review.platform_name]}
                          <span className={`px-2 py-0.5 ${badge.bg} ${badge.text} rounded text-[9px] font-bold uppercase tracking-tight whitespace-nowrap`}>
                            {review.platform_name}
                          </span>
                        </span>
                      </td>

                      {/* Date */}
                      <td className="px-4 py-4 text-xs font-bold text-on-surface select-none whitespace-nowrap">
                        {formatDate(review.scraped_at).split(",")[0]}
                        <span className="text-on-surface-variant/60 font-medium font-mono text-[10px] ml-1">
                          ,{formatDate(review.scraped_at).split(",")[1]}
                        </span>
                      </td>

                      {/* Review Text */}
                      <td className="px-4 py-4">
                        <div className="flex flex-col gap-1.5">
                          <p className="text-xs text-on-surface font-medium leading-relaxed max-w-[600px] truncate">
                            {(review.platform_name === "Ekşi Sözlük" || review.platform_name === "Şikayetvar") && review.subject ? (
                              <>
                                <strong className="font-bold mr-1">[{review.subject}]</strong>
                                {highlightText(review.original_text.substring(0, 120), searchQuery)}
                              </>
                            ) : (
                              highlightText(review.original_text.substring(0, 120), searchQuery)
                            )}
                            {review.original_text.length > 120 ? "..." : ""}
                          </p>
                          {isChurn && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#fde8e8] text-[#c53030] rounded-md text-[10px] font-bold w-fit">
                              <span className="material-symbols-outlined text-xs">warning</span>
                              Yüksek Risk
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Category + Keywords */}
                      <td className="px-4 py-4">
                        <div className="flex flex-col gap-1">
                          <span className="bg-[#ede6f0] text-on-surface font-semibold px-2.5 py-0.5 rounded text-[11px] inline-block w-fit">
                            {review.category}
                          </span>
                          {review.keywords && review.keywords.length > 0 && (
                            <div className="flex gap-1 flex-wrap mt-0.5">
                              {review.keywords.map((kw) => (
                                <span key={kw} className="text-[10px] font-semibold bg-[#eaddff] text-secondary px-1.5 py-0.5 rounded">
                                  {kw}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Sentiment */}
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 rounded-md text-[11px] font-bold ${sentiment.class}`}>
                          {sentiment.label}
                        </span>
                      </td>
                    </tr>

                    {/* Expanded */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={5} className="bg-[#f8f1fc] p-6 border-b border-outline-variant">
                          <div className="flex flex-col gap-4 pl-6 pr-6">
                            <div className="flex items-center justify-between text-xs text-on-surface-variant border-b border-outline-variant/30 pb-3">
                              <div className="flex items-center gap-4">
                                <span className="flex items-center gap-1.5 font-bold">
                                  <User size={14} /> {review.author || "Anonim"}
                                </span>
                                <span className="flex items-center gap-1.5 font-semibold text-on-surface-variant/80">
                                  <Clock size={14} />
                                  {new Date(review.scraped_at).toLocaleDateString("tr-TR", {
                                    day: "2-digit", month: "short", year: "numeric",
                                    hour: "2-digit", minute: "2-digit",
                                  })}
                                </span>
                              </div>
                              {review.rating !== null && review.rating !== undefined && (
                                <span className="font-bold bg-white px-2 py-1 rounded-lg border border-outline-variant text-[#220053]">
                                  Skor: {review.rating} / 5
                                </span>
                              )}
                            </div>

                            <div className="space-y-2">
                              {review.subject && (
                                <h4 className="text-sm font-bold text-primary">{review.subject}</h4>
                              )}
                              <p className="text-xs text-on-surface leading-relaxed whitespace-pre-wrap font-medium">
                                {highlightText(review.original_text, searchQuery)}
                              </p>
                            </div>

                            {review.source_url && (
                              <div className="pt-2 flex justify-start">
                                <a
                                  href={review.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-white border border-outline-variant text-[#6b38d4] hover:bg-[#6b38d4] hover:text-white shadow-sm transition-all duration-200"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <LinkSimpleHorizontal size={14} weight="bold" />
                                  Kaynağa Git
                                </a>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
