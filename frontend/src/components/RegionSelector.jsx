import { useState, useRef, useEffect } from "react";

/**
 * REGIONS config with design tokens matching the provided reference images.
 * Colors are curated for a premium, high-contrast dark theme look.
 */
export const REGIONS = [
  { id: "na1",  label: "NA",   color: "text-[#b088cc]", bg: "bg-[#b088cc]/10", border: "border-[#b088cc]/25", glow: "shadow-[#b088cc]/30" },
  { id: "euw1", label: "EUW",  color: "text-[#4299e1]", bg: "bg-[#4299e1]/10", border: "border-[#4299e1]/30", glow: "shadow-[#4299e1]/50" },
  { id: "eun1", label: "EUNE", color: "text-[#718096]", bg: "bg-[#718096]/10", border: "border-[#718096]/20", glow: "shadow-[#718096]/20" },
  { id: "kr",   label: "KR",   color: "text-[#319795]", bg: "bg-[#319795]/10", border: "border-[#319795]/30", glow: "shadow-[#319795]/40" },
  { id: "jp1",  label: "JP",   color: "text-[#d53f8c]", bg: "bg-[#d53f8c]/10", border: "border-[#d53f8c]/25", glow: "shadow-[#d53f8c]/30" },
  { id: "br1",  label: "BR",   color: "text-[#38a169]", bg: "bg-[#38a169]/10", border: "border-[#38a169]/30", glow: "shadow-[#38a169]/30" },
  { id: "la1",  label: "LAN",  color: "text-[#d69e2e]", bg: "bg-[#d69e2e]/10", border: "border-[#d69e2e]/25", glow: "shadow-[#d69e2e]/30" },
  { id: "la2",  label: "LAS",  color: "text-[#dd6b20]", bg: "bg-[#dd6b20]/10", border: "border-[#dd6b20]/25", glow: "shadow-[#dd6b20]/30" },
  { id: "oc1",  label: "OCE",  color: "text-[#68d391]", bg: "bg-[#68d391]/10", border: "border-[#68d391]/25", glow: "shadow-[#68d391]/20" },
  { id: "tr1",  label: "TR",   color: "text-[#e53e3e]", bg: "bg-[#e53e3e]/10", border: "border-[#e53e3e]/30", glow: "shadow-[#e53e3e]/40" },
  { id: "ru",   label: "RU",   color: "text-[#9f7aea]", bg: "bg-[#9f7aea]/10", border: "border-[#9f7aea]/25", glow: "shadow-[#9f7aea]/30" },
  { id: "ph2",  label: "PH",   color: "text-[#2c7a7b]", bg: "bg-[#2c7a7b]/10", border: "border-[#2c7a7b]/25", glow: "shadow-[#2c7a7b]/30" },
  { id: "sg2",  label: "SG",   color: "text-[#b83280]", bg: "bg-[#b83280]/10", border: "border-[#b83280]/25", glow: "shadow-[#b83280]/30" },
  { id: "th2",  label: "TH",   color: "text-[#2f855a]", bg: "bg-[#2f855a]/10", border: "border-[#2f855a]/25", glow: "shadow-[#2f855a]/30" },
  { id: "tw2",  label: "TW",   color: "text-[#d69e2e]", bg: "bg-[#d69e2e]/15", border: "border-[#d69e2e]/30", glow: "shadow-[#d69e2e]/40" },
  { id: "vn2",  label: "VN",   color: "text-[#975a2a]", bg: "bg-[#975a2a]/15", border: "border-[#975a2a]/30", glow: "shadow-[#975a2a]/30" },
];

export default function RegionSelector({ value, onChange, compact = false }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  
  const activeRegion = REGIONS.find(r => r.id === value) || REGIONS[0];

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleDropdown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsOpen(!isOpen);
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={toggleDropdown}
        className={`flex items-center gap-2 group transition-all duration-200 outline-none
          ${compact 
            ? "h-full px-2" 
            : "w-full min-w-[120px] px-4 py-3 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.04] hover:bg-slate-50 dark:hover:bg-white/[0.06] shadow-sm active:scale-[0.98]"
          }`}
      >
        <div className="flex items-center gap-1.5 flex-1">
          {/* Representative Chip */}
          <span className={`text-[10px] font-black tracking-widest px-1.5 py-0.5 rounded border pointer-events-none
            ${activeRegion.color} ${activeRegion.bg} ${activeRegion.border} shadow-sm z-10 transition-transform group-hover:scale-105`}
          >
            {activeRegion.label}
          </span>
          {!compact && (
            <span className="text-sm font-bold text-slate-700 dark:text-white/80 select-none">
              {activeRegion.label}
            </span>
          )}
        </div>
        
        {/* Always visible arrow */}
        <svg 
          className={`w-3 h-3 text-slate-400 dark:text-white/20 transition-transform duration-300 flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`}
          viewBox="0 0 16 16" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2.5" 
          strokeLinecap="round" 
          strokeLinejoin="round"
        >
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-3 z-[200] w-64 p-3
          bg-white dark:bg-[#0d111a] 
          border border-slate-200 dark:border-white/[0.12]
          rounded-2xl shadow-2xl shadow-black/80
          animate-fadeIn transform origin-top-left backdrop-blur-md"
        >
          <div className="mb-2 px-1 text-[9px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/20">
            Select Server
          </div>
          <div className="grid grid-cols-3 gap-1.5 overflow-y-auto max-h-[300px] custom-scrollbar">
            {REGIONS.map((r) => {
              const isActive = r.id === value;
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => {
                    onChange(r.id);
                    setIsOpen(false);
                  }}
                  className={`flex items-center justify-center h-9 rounded-lg text-[9px] font-black tracking-widest border transition-all duration-200
                    ${isActive 
                      ? `${r.color} ${r.bg} ${r.border} ${r.glow} ring-1 ring-white/10 scale-[1.05] z-10 
                         shadow-[0_0_15px_-3px] current-shadow` 
                      : "text-slate-500 dark:text-white/30 border-transparent hover:bg-slate-100 dark:hover:bg-white/5 hover:text-slate-800 dark:hover:text-white/60"
                    }`}
                  style={isActive ? { '--tw-shadow-color': 'currentColor' } : {}}
                >
                  {r.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Tailwind helper for glow if not defined in main css */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .animate-fadeIn { animation: fadeIn 0.15s ease-out forwards; }
        .current-shadow { box-shadow: 0 0 15px -3px var(--tw-shadow-color); }
      `}} />
    </div>
  );
}
