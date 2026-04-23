import { useState, useRef, useEffect } from "react";
import { REGIONS } from "../utils/regions";

/**
 * RegionSelector — Sleek, compact region picker.
 * 
 * Redesigned from a bulky 3-column grid to a polished single-column
 * scrollable list with region-colored accents and search filtering.
 */

const POPULAR_IDS = ["na1", "euw1", "kr", "eun1", "br1", "jp1"];

export default function RegionSelector({ value, onChange, compact = false, pill = false }) {
  const [isOpen, setIsOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const dropdownRef = useRef(null);
  const filterRef = useRef(null);
  
  const activeRegion = REGIONS.find(r => r.id === value) || REGIONS[0];

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setFilter("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && filterRef.current) {
      filterRef.current.focus();
    }
  }, [isOpen]);

  const toggleDropdown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsOpen(!isOpen);
    if (isOpen) setFilter("");
  };

  const popular = REGIONS.filter(r => POPULAR_IDS.includes(r.id));
  const others = REGIONS.filter(r => !POPULAR_IDS.includes(r.id));

  const filteredRegions = filter
    ? REGIONS.filter(r => 
        r.label.toLowerCase().includes(filter.toLowerCase()) || 
        r.id.toLowerCase().includes(filter.toLowerCase())
      )
    : null;

  const handleSelect = (r) => {
    onChange(r.id);
    setIsOpen(false);
    setFilter("");
  };

  const RegionButton = ({ r }) => {
    const isActive = r.id === value;
    return (
      <button
        key={r.id}
        type="button"
        onClick={() => handleSelect(r)}
        className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left transition-all duration-150
          ${isActive 
            ? `${r.bg} ${r.border} border shadow-sm` 
            : "border border-transparent hover:bg-slate-100/80 dark:hover:bg-white/[0.04]"
          }`}
      >
        <span className={`text-[9px] font-black tracking-widest w-10 text-center py-0.5 rounded border shrink-0
          ${isActive 
            ? `${r.color} ${r.bg} ${r.border}` 
            : "text-slate-400 dark:text-white/25 bg-slate-100 dark:bg-white/[0.04] border-slate-200 dark:border-white/[0.06]"
          }`}
        >
          {r.label}
        </span>
        <span className={`text-xs font-medium truncate
          ${isActive ? `${r.color}` : "text-slate-500 dark:text-white/40"}`}
        >
          {r.id.toUpperCase()}
        </span>
        {isActive && (
          <svg className={`w-3 h-3 ml-auto ${r.color} shrink-0`} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3.5 8.5l3 3 6-7" />
          </svg>
        )}
      </button>
    );
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
        <div className={`absolute top-full left-0 mt-2 z-[200] w-56
          bg-white dark:bg-[#0d111a] 
          border border-slate-200 dark:border-white/[0.10]
          rounded-xl shadow-2xl shadow-black/60
          animate-dropdownFadeIn transform origin-top-left backdrop-blur-xl
          overflow-hidden`}
        >
          {/* Search filter */}
          <div className="px-3 pt-3 pb-2">
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-300 dark:text-white/15 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
              </svg>
              <input
                ref={filterRef}
                type="text"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter..."
                className="w-full bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.06] rounded-lg 
                  pl-8 pr-3 py-1.5 text-xs text-slate-700 dark:text-white/70 
                  placeholder:text-slate-300 dark:placeholder:text-white/15
                  outline-none focus:border-[#c89b3c]/40 transition-colors"
              />
            </div>
          </div>

          <div className="max-h-[280px] overflow-y-auto custom-scrollbar px-2 pb-2">
            {filteredRegions ? (
              /* Filtered results */
              filteredRegions.length > 0 ? (
                <div className="space-y-0.5">
                  {filteredRegions.map(r => <RegionButton key={r.id} r={r} />)}
                </div>
              ) : (
                <p className="text-center text-xs text-slate-400 dark:text-white/15 py-6 italic">No region found</p>
              )
            ) : (
              /* Default: Popular + Others */
              <>
                <div className="mb-1">
                  <span className="text-[8px] font-black uppercase tracking-[0.2em] text-slate-300 dark:text-white/10 px-3 py-1 block">
                    Popular
                  </span>
                  <div className="space-y-0.5">
                    {popular.map(r => <RegionButton key={r.id} r={r} />)}
                  </div>
                </div>
                <div className="border-t border-slate-100 dark:border-white/[0.04] pt-1 mt-1">
                  <span className="text-[8px] font-black uppercase tracking-[0.2em] text-slate-300 dark:text-white/10 px-3 py-1 block">
                    Other
                  </span>
                  <div className="space-y-0.5">
                    {others.map(r => <RegionButton key={r.id} r={r} />)}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
