"use client";

import React, { useEffect, useState } from "react";
import { format } from "date-fns";
import { tr } from "date-fns/locale";

interface PlatformStats {
  [platform: string]: {
    new_reviews: number;
    duration_seconds: number;
    error?: string;
  };
}

interface ScraperLog {
  id: string;
  started_at: string;
  completed_at: string;
  total_duration_seconds: number;
  status: "success" | "error";
  error_message: string | null;
  platform_stats: PlatformStats;
}

interface ScraperLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ScraperLogsModal({ isOpen, onClose }: ScraperLogsModalProps) {
  const [logs, setLogs] = useState<ScraperLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      fetch("/api/logs")
        .then((res) => res.json())
        .then((data) => {
          if (data.logs) {
            setLogs(data.logs);
          }
        })
        .catch((err) => console.error("Failed to load logs:", err))
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-5xl max-h-[90vh] bg-slate-900 border border-slate-700 shadow-2xl rounded-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Sistem ve Scraper Logları
            </h2>
            <p className="text-sm text-slate-400 mt-1">Son 50 çalışma kaydı</p>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-full hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 bg-slate-900">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400">
              <svg className="w-8 h-8 animate-spin mb-4 text-indigo-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Loglar Yükleniyor...</span>
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-20 text-slate-400">
              Henüz kaydedilmiş log bulunmamaktadır.
            </div>
          ) : (
            <div className="space-y-4">
              {logs.map((log) => {
                const startDate = new Date(log.started_at);
                const isSuccess = log.status === "success";
                
                return (
                  <div 
                    key={log.id} 
                    className="border border-slate-800 bg-slate-800/30 rounded-xl overflow-hidden hover:border-slate-700 transition-colors"
                  >
                    <div className="flex flex-wrap items-center justify-between p-4 bg-slate-800/50 gap-4">
                      <div className="flex items-center gap-4">
                        <div className={`p-2 rounded-full ${isSuccess ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                          {isSuccess ? (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                          ) : (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          )}
                        </div>
                        <div>
                          <div className="text-slate-200 font-medium">
                            {format(startDate, "d MMMM yyyy, HH:mm", { locale: tr })}
                          </div>
                          <div className="text-sm text-slate-400">
                            Toplam Süre: <span className="text-slate-300 font-medium">{log.total_duration_seconds}s</span>
                          </div>
                        </div>
                      </div>
                      
                      {/* Summary Badges */}
                      <div className="flex gap-2">
                        {Object.entries(log.platform_stats).map(([platform, stats]) => {
                          const hasNew = stats.new_reviews > 0;
                          return (
                            <div key={platform} className={`px-2.5 py-1 rounded-md text-xs font-medium border ${hasNew ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-300' : 'bg-slate-800 border-slate-700 text-slate-400'}`}>
                              {platform}: {stats.new_reviews}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                    
                    {/* Platform Details Table */}
                    <div className="p-4 border-t border-slate-800">
                      <table className="w-full text-sm text-left">
                        <thead className="text-xs text-slate-400 uppercase bg-slate-900/50">
                          <tr>
                            <th className="px-4 py-2 font-medium rounded-tl-lg">Platform</th>
                            <th className="px-4 py-2 font-medium">Yeni Yorum</th>
                            <th className="px-4 py-2 font-medium">Süre</th>
                            <th className="px-4 py-2 font-medium rounded-tr-lg">Durum</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(log.platform_stats).map(([platform, stats], idx) => (
                            <tr key={platform} className="border-b border-slate-800/50 last:border-0">
                              <td className="px-4 py-3 text-slate-300 font-medium">{platform}</td>
                              <td className="px-4 py-3 text-slate-300">
                                {stats.new_reviews > 0 ? (
                                  <span className="text-emerald-400 font-semibold">+{stats.new_reviews}</span>
                                ) : "0"}
                              </td>
                              <td className="px-4 py-3 text-slate-400">{stats.duration_seconds}s</td>
                              <td className="px-4 py-3">
                                {stats.error ? (
                                  <span className="text-rose-400 text-xs truncate max-w-[200px] block" title={stats.error}>
                                    Hata: {stats.error}
                                  </span>
                                ) : (
                                  <span className="text-emerald-400/80 text-xs">Başarılı</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      
                      {!isSuccess && log.error_message && (
                        <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg">
                          <h4 className="text-rose-400 text-sm font-semibold mb-1">Kritik Hata</h4>
                          <p className="text-rose-300/80 text-sm font-mono break-all">{log.error_message}</p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
