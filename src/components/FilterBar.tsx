"use client";

import type { Filters } from "./Dashboard";
import { Funnel, Trash } from "@phosphor-icons/react";

const PLATFORMS = [
  { value: "all", label: "Tüm Platformlar" },
  { value: "Play Store", label: "Play Store" },
  { value: "App Store", label: "App Store" },
  { value: "Şikayetvar", label: "Şikayetvar" },
  { value: "Ekşi Sözlük", label: "Ekşi Sözlük" },
];

const SENTIMENTS = [
  { value: "all", label: "Tüm Duygular" },
  { value: "Positive", label: "Pozitif" },
  { value: "Negative", label: "Negatif" },
  { value: "Neutral", label: "Nötr" },
];

const CATEGORIES = [
  { value: "all", label: "Tüm Konular" },
  { value: "Abonelik", label: "Abonelik" },
  { value: "Adres Değişikliği", label: "Adres Değişikliği" },
  { value: "ADSL", label: "ADSL" },
  { value: "Altyapı", label: "Altyapı" },
  { value: "Altyapısız İnternet", label: "Altyapısız İnternet" },
  { value: "Arıza", label: "Arıza" },
  { value: "Bakım Çalışması", label: "Bakım Çalışması" },
  { value: "Dondurma İşlemi", label: "Dondurma İşlemi" },
  { value: "Ev Telefonu Hizmeti", label: "Ev Telefonu Hizmeti" },
  { value: "Evde İnternet", label: "Evde İnternet" },
  { value: "Fatura", label: "Fatura" },
  { value: "Fiber İnternet", label: "Fiber İnternet" },
  { value: "Gezgin İnternet", label: "Gezgin İnternet" },
  { value: "Gigafiber", label: "Gigafiber" },
  { value: "Hız Testi", label: "Hız Testi" },
  { value: "İnternet Kesintisi", label: "İnternet Kesintisi" },
  { value: "İnternet Paketleri", label: "İnternet Paketleri" },
  { value: "Modem", label: "Modem" },
  { value: "Online İşlemler", label: "Online İşlemler" },
  { value: "Ping Sorunu", label: "Ping Sorunu" },
  { value: "VDSL", label: "VDSL" },
  { value: "Yalın İnternet", label: "Yalın İnternet" },
  { value: "Genel", label: "Genel" }
];

interface FilterBarProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export default function FilterBar({ filters, onChange }: FilterBarProps) {
  const handleChange = (key: keyof Filters, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  const handleReset = () => {
    onChange({ platform: "all", sentiment: "all", category: "all", dateFrom: "", dateTo: "" });
  };

  const hasActiveFilters =
    filters.platform !== "all" ||
    filters.sentiment !== "all" ||
    filters.category !== "all" ||
    filters.dateFrom !== "" ||
    filters.dateTo !== "";

  return (
    <div className="bento-card p-8 flex flex-col gap-6">
      <div className="flex items-center gap-2 text-text-muted">
        <Funnel size={18} weight="regular" className="text-brand-accent" />
        <h2 className="text-[10px] font-semibold tracking-wider uppercase">Filtreleme Seçenekleri</h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-6 items-end">
        {/* Platform filter */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Platform
          </label>
          <select
            value={filters.platform}
            onChange={(e) => handleChange("platform", e.target.value)}
            className="w-full bg-slate-50 border border-slate-200/80 text-brand-primary text-xs py-3 px-4 rounded-2xl focus:outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-accent/10 transition-all appearance-none cursor-pointer"
          >
            {PLATFORMS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        {/* Category filter */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Şikayet Konusu
          </label>
          <select
            value={filters.category}
            onChange={(e) => handleChange("category", e.target.value)}
            className="w-full bg-slate-50 border border-slate-200/80 text-brand-primary text-xs py-3 px-4 rounded-2xl focus:outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-accent/10 transition-all appearance-none cursor-pointer"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        {/* Sentiment filter */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Duygu Durumu
          </label>
          <select
            value={filters.sentiment}
            onChange={(e) => handleChange("sentiment", e.target.value)}
            className="w-full bg-slate-50 border border-slate-200/80 text-brand-primary text-xs py-3 px-4 rounded-2xl focus:outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-accent/10 transition-all appearance-none cursor-pointer"
          >
            {SENTIMENTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Date from */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Başlangıç Tarihi
          </label>
          <input
            type="date"
            value={filters.dateFrom}
            onChange={(e) => handleChange("dateFrom", e.target.value)}
            className="w-full bg-slate-50 border border-slate-200/80 text-brand-primary text-xs py-3 px-4 rounded-2xl focus:outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-accent/10 transition-all cursor-text"
          />
        </div>

        {/* Date to */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Bitiş Tarihi
          </label>
          <input
            type="date"
            value={filters.dateTo}
            onChange={(e) => handleChange("dateTo", e.target.value)}
            className="w-full bg-slate-50 border border-slate-200/80 text-brand-primary text-xs py-3 px-4 rounded-2xl focus:outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-accent/10 transition-all cursor-text"
          />
        </div>
      </div>

      {hasActiveFilters && (
        <div className="flex justify-end pt-2 border-t border-slate-100">
          <button
            onClick={handleReset}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-2xl border border-slate-200 text-text-muted hover:text-sentiment-neg hover:border-sentiment-neg/20 hover:bg-red-50 transition-all cursor-pointer"
          >
            <Trash size={14} />
            Filtreleri Temizle
          </button>
        </div>
      )}
    </div>
  );
}
