import { useTheme } from "../hooks/useTheme";

/**
 * ThemeToggle — Polished sun/moon toggle with smooth transition.
 */
export default function ThemeToggle() {
  const { dark, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      className="relative flex items-center justify-center w-9 h-9 rounded-xl 
        bg-slate-100 dark:bg-white/[0.06] 
        border border-slate-200/80 dark:border-white/[0.08]
        hover:bg-slate-200 dark:hover:bg-white/[0.1]
        active:scale-95 transition-all duration-200
        group"
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {/* Sun icon (visible in dark mode) */}
      <svg 
        className={`w-4 h-4 absolute transition-all duration-300
          ${dark 
            ? "opacity-100 rotate-0 scale-100 text-[#c89b3c]" 
            : "opacity-0 -rotate-90 scale-50 text-[#c89b3c]"
          }`}
        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="5" />
        <line x1="12" y1="1" x2="12" y2="3" />
        <line x1="12" y1="21" x2="12" y2="23" />
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        <line x1="1" y1="12" x2="3" y2="12" />
        <line x1="21" y1="12" x2="23" y2="12" />
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
      </svg>

      {/* Moon icon (visible in light mode) */}
      <svg 
        className={`w-4 h-4 absolute transition-all duration-300
          ${dark 
            ? "opacity-0 rotate-90 scale-50 text-slate-500" 
            : "opacity-100 rotate-0 scale-100 text-slate-500"
          }`}
        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      >
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
    </button>
  );
}
