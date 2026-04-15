import { useState, useRef, useEffect } from "react";
import { REGIONS } from "../utils/regions";

export default function RegionSelector({ value, onChange, compact = false, pill = false }) {
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
      {pill ? (
        <button
          type="button"
          onClick={toggleDropdown}
          className={`flex items-center gap-1.5 pl-3.5 pr-2.5 h-full transition-all rounded-l-xl
            border-r border-slate-200 dark:border-white/10
            bg-slate-50 dark:bg-white/[0.04] hover:bg-slate-100 dark:hover:bg-white/[0.08]
            group select-none`}
        >
          <span className={`text-[10px] font-black tracking-widest px-1.5 py-0.5 rounded border 
            ${activeRegion.color} ${activeRegion.bg} ${activeRegion.border} 
            transition-transform group-hover:scale-105 pointer-events-none`}
          >
            {activeRegion.label}
          </span>
          <svg 
            className={`w-3 h-3 text-slate-400 dark:text-white/20 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}
            viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          >
            <path d="M4 6l4 4 4-4" />
          </svg>
        </button>
      ) : (
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
            <span className={`text-[10px] font-black tracking-widest px-1.5 py-0.5 rounded border pointer-events-none
              ${activeRegion.color} ${activeRegion.bg} ${activeRegion.border} shadow-sm transition-transform group-hover:scale-105`}
            >
              {activeRegion.label}
            </span>
            {!compact && (
              <span className="text-sm font-bold text-slate-700 dark:text-white/80 select-none">
                {activeRegion.label}
              </span>
            )}
          </div>
          <svg 
            className={`w-3 h-3 text-slate-400 dark:text-white/20 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}
            viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          >
            <path d="M4 6l4 4 4-4" />
          </svg>
        </button>
      )}

      {/* Dropdown Menu */}
      {isOpen && (
        <div className={`absolute top-full left-0 mt-3 z-[200] w-64 p-3
          bg-white dark:bg-[#0d111a] 
          border border-slate-200 dark:border-white/[0.12]
          rounded-2xl shadow-2xl shadow-black/80
          animate-fadeIn transform origin-top-left backdrop-blur-md`}
        >
          <div className="mb-2.5 px-1 flex items-center justify-between">
            <span className="text-[9px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/20">
              Select Client
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#c89b3c]/40 animate-pulse" />
          </div>
          <div className="grid grid-cols-3 gap-1.5 overflow-y-auto max-h-[320px] custom-scrollbar pr-1">
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
                  className={`flex items-center justify-center h-10 rounded-lg text-[9px] font-black tracking-widest border transition-all duration-200
                    ${isActive 
                      ? `${r.color} ${r.bg} ${r.border} shadow-[0_0_15px_-3px] current-shadow ring-1 ring-white/10 scale-[1.05] z-10` 
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
