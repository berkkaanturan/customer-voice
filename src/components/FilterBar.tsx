"use client";

import { useState, useRef, useEffect } from "react";
import { GooglePlayLogo, Megaphone, Quotes, SquaresFour, CaretDown } from "@phosphor-icons/react";

const PLATFORMS = [
  { value: "all", label: "Tümü" },
  { value: "Şikayetvar", label: "Şikayetvar" },
  { value: "App Store", label: "App Store" },
  { value: "Play Store", label: "Play Store" },
  { value: "Ekşi Sözlük", label: "Ekşi Sözlük" },
];

const AppStoreIcon = () => (
  <svg width="14" height="14" viewBox="0 0 640 640" className="text-blue-600 inline-block align-middle fill-current shrink-0">
    <path d="m319.9 184.9l9.1-15.7c5.6-9.8 18.1-13.1 27.9-7.5s13.1 18.1 7.5 27.9l-87.5 151.5h63.3c20.5 0 32 24.1 23.1 40.8H177.8c-11.3 0-20.4-9.1-20.4-20.4s9.1-20.4 20.4-20.4h52l66.6-115.4l-20.8-36.1c-5.6-9.8-2.3-22.2 7.5-27.9c9.8-5.6 22.2-2.3 27.9 7.5zm-78.7 218l-19.6 34c-5.6 9.8-18.1 13.1-27.9 7.5s-13.1-18.1-7.5-27.9l14.6-25.2c16.4-5.1 29.8-1.2 40.4 11.6m168.9-61.7h53.1c11.3 0 20.4 9.1 20.4 20.4s-9.1 20.4-20.4 20.4h-29.5l19.9 34.5c5.6 9.8 2.3 22.2-7.5 27.9c-9.8 5.6-22.2 2.3-27.9-7.5c-33.5-58.1-58.7-101.6-75.4-130.6c-17.1-29.5-4.9-59.1 7.2-69.1c13.4 23 33.4 57.7 60.1 104M320 72C183 72 72 183 72 320s111 248 248 248s248-111 248-248S457 72 320 72M104 320c0-119.3 96.7-216 216-216s216 96.7 216 216s-96.7 216-216 216s-216-96.7-216-216" />
  </svg>
);

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  all: <SquaresFour size={14} weight="regular" className="text-slate-500" />,
  "Şikayetvar": <Megaphone size={14} weight="regular" className="text-blue-600" />,
  "App Store": <AppStoreIcon />,
  "Play Store": <GooglePlayLogo size={14} weight="regular" className="text-emerald-600" />,
  "Ekşi Sözlük": <Quotes size={14} weight="regular" className="text-orange-600" />,
};

interface FilterBarProps {
  platform: string;
  onChange: (platform: string) => void;
}

export default function FilterBar({ platform, onChange }: FilterBarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const activePlatform = PLATFORMS.find(p => p.value === platform) || PLATFORMS[0];

  return (
    <>
      {/* Mobile Dropdown View */}
      <div className="relative md:hidden shrink-0" ref={dropdownRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-container-low border border-outline-variant/20 rounded-lg text-xs font-bold text-[#220053] shadow-xs hover:bg-slate-50 transition-colors"
        >
          {PLATFORM_ICONS[activePlatform.value]}
          <span>{activePlatform.label}</span>
          <CaretDown size={12} weight="bold" className={`text-on-surface-variant transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
        </button>

        {isOpen && (
          <div className="absolute right-0 top-full mt-2 w-40 bg-white border border-outline-variant/20 rounded-xl shadow-lg z-50 overflow-hidden py-1">
            {PLATFORMS.map((p) => (
              <button
                key={p.value}
                onClick={() => {
                  onChange(p.value);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-slate-50 transition-colors ${
                  platform === p.value ? "text-[#220053] font-bold bg-slate-50" : "text-on-surface-variant font-medium"
                }`}
              >
                {PLATFORM_ICONS[p.value]}
                <span>{p.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Desktop Pills View */}
      <div className="hidden md:flex overflow-x-auto items-center bg-surface-container-low rounded-lg p-1 border border-outline-variant/10 w-auto [&::-webkit-scrollbar]:hidden">
        {PLATFORMS.map((p) => {
          const isActive = platform === p.value;
          return (
            <button
              key={p.value}
              onClick={() => onChange(p.value)}
              className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 cursor-pointer flex items-center gap-1.5 ${
                isActive
                  ? "bg-white shadow-xs text-[#220053] font-bold"
                  : "text-[#4a4452] hover:text-[#220053]"
              }`}
            >
              {PLATFORM_ICONS[p.value]}
              <span>{p.label}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}
