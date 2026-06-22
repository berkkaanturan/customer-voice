import { useState, Fragment } from "react";
import type { Review } from "@/lib/supabase";
import {
  AppleLogo,
  GooglePlayLogo,
  Megaphone,
  Quotes,
  LinkSimpleHorizontal,
  Tray,
  ChatCircle,
  Clock,
  User,
  CaretDown,
  CaretUp
} from "@phosphor-icons/react";

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  "Play Store": <GooglePlayLogo size={18} weight="regular" className="text-emerald-600" />,
  "App Store": <AppleLogo size={18} weight="regular" className="text-slate-700" />,
  "Şikayetvar": <Megaphone size={18} weight="regular" className="text-amber-600" />,
  "Ekşi Sözlük": <Quotes size={18} weight="regular" className="text-green-700" />,
};

const SENTIMENT_BADGE: Record<string, { class: string; label: string }> = {
  Positive: { class: "bg-emerald-50 text-emerald-700 border-emerald-200/60", label: "Pozitif" },
  Negative: { class: "bg-red-50 text-red-700 border-red-200/60", label: "Negatif" },
  Neutral: { class: "bg-amber-50 text-amber-700 border-amber-200/60", label: "Nötr" },
};

interface ReviewTableProps {
  reviews: Review[];
  loading: boolean;
  onMarkRead: (id: string) => void;
}

export default function ReviewTable({
  reviews,
  loading,
  onMarkRead,
}: ReviewTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (review: Review) => {
    setExpandedId((prev) => (prev === review.id ? null : review.id));
    if (!review.is_read) {
      onMarkRead(review.id);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const truncateText = (text: string, maxLen = 120) => {
    if (text.length <= maxLen) return text;
    return text.substring(0, maxLen) + "...";
  };

  if (loading) {
    return (
      <div className="p-8 space-y-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="shimmer-skeleton h-14 w-full rounded-2xl" />
        ))}
      </div>
    );
  }

  if (reviews.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-text-muted">
        <Tray size={48} weight="light" className="text-text-light mb-4" />
        <p className="text-sm font-semibold">Sonuç bulunamadı</p>
        <p className="text-xs mt-1">Filtrelerinizi değiştirmeyi deneyin</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto w-full">
      <table className="premium-table">
        <thead>
          <tr className="border-b border-slate-100">
            <th style={{ width: 40 }} className="pl-6"></th>
            <th style={{ width: 140 }}>Platform</th>
            <th>Yorum Detayı</th>
            <th style={{ width: 120 }}>Kategori</th>
            <th style={{ width: 100 }}>Duygu</th>
            <th style={{ width: 150 }} className="pr-6">Tarih</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((review) => {
            const isExpanded = expandedId === review.id;
            const sentiment = SENTIMENT_BADGE[review.sentiment] || SENTIMENT_BADGE.Neutral;
            const icon = PLATFORM_ICONS[review.platform_name] || <ChatCircle size={18} />;

            return (
              <Fragment key={review.id}>
                <tr
                  className={`cursor-pointer hover:bg-slate-50/50 ${
                    !review.is_read ? "bg-blue-50/20 font-semibold" : ""
                  }`}
                  onClick={() => toggleExpand(review)}
                >
                  {/* Read indicator */}
                  <td className="text-center pl-6 py-4">
                    {!review.is_read && (
                      <span className="w-2.5 h-2.5 rounded-full bg-brand-accent inline-block" />
                    )}
                  </td>

                  {/* Platform */}
                  <td className="py-4">
                    <div className="flex items-center gap-2">
                      {icon}
                      <span className="text-xs text-text-muted font-medium">
                        {review.platform_name}
                      </span>
                    </div>
                  </td>

                  {/* Comment Text Summary */}
                  <td className="max-w-[450px] py-4 pr-4">
                    <div className="flex flex-col gap-1">
                      {review.subject && (
                        <span className="text-xs font-bold text-brand-primary line-clamp-1">
                          {review.subject}
                        </span>
                      )}
                      <p className={`text-xs leading-relaxed line-clamp-2 ${
                        !review.is_read ? "text-brand-primary" : "text-text-muted"
                      }`}>
                        {truncateText(review.original_text)}
                      </p>
                      {review.author && (
                        <span className="text-[10px] text-text-light">
                          {review.author}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Category */}
                  <td className="py-4">
                    <span className="inline-flex items-center px-2.5 py-1 rounded-xl text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200/50">
                      {review.category}
                    </span>
                  </td>

                  {/* Sentiment */}
                  <td className="py-4">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-xl text-[10px] font-semibold border ${sentiment.class}`}>
                      {sentiment.label}
                    </span>
                  </td>

                  {/* Date */}
                  <td className="py-4 pr-6 text-xs text-text-muted font-mono whitespace-nowrap">
                    {formatDate(review.scraped_at)}
                  </td>
                </tr>

                {/* Expanded content view */}
                {isExpanded && (
                  <tr>
                    <td colSpan={6} className="bg-slate-50/40 p-6 border-b border-slate-100">
                      <div className="flex flex-col gap-4 pl-10 pr-6">
                        <div className="flex items-center justify-between text-xs text-text-light border-b border-slate-100 pb-3">
                          <div className="flex items-center gap-4">
                            <span className="flex items-center gap-1.5">
                              <User size={14} />
                              {review.author || "Anonim"}
                            </span>
                            <span className="flex items-center gap-1.5 font-mono">
                              <Clock size={14} />
                              {formatDate(review.scraped_at)}
                            </span>
                          </div>
                          {review.rating !== null && review.rating !== undefined && (
                            <span className="font-mono font-bold bg-white px-2 py-1 rounded-lg border border-slate-200">
                              Skor: {review.rating} / 5
                            </span>
                          )}
                        </div>

                        <div className="space-y-2">
                          {review.subject && (
                            <h4 className="text-sm font-bold text-brand-primary">
                              {review.subject}
                            </h4>
                          )}
                          <p className="text-xs text-text-main leading-relaxed whitespace-pre-wrap">
                            {review.original_text}
                          </p>
                        </div>

                        {review.source_url && (
                          <div className="pt-2 flex justify-start">
                            <a
                              href={review.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-2xl bg-white border border-slate-200 text-brand-accent hover:bg-brand-accent hover:text-white hover:border-brand-accent shadow-sm transition-all duration-200"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <LinkSimpleHorizontal size={14} weight="bold" />
                              Yorumu Yerinde Oku (Kaynağa Git)
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
  );
}
