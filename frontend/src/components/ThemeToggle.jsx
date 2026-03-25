import { useTheme } from "../context/ThemeContext";

export default function ThemeToggle() {
  const { dark, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      className="relative flex items-center h-8 rounded-full p-0.5 transition-colors duration-300
        bg-slate-200 dark:bg-white/10 border border-slate-300/60 dark:border-white/10"
      aria-label="Toggle theme"
    >
      <span
        className={`absolute h-7 rounded-full transition-all duration-300 bg-white dark:bg-[#c89b3c]/90 shadow-sm
          ${dark ? "left-[calc(50%-1px)] right-0.5" : "left-0.5 right-[calc(50%-1px)]"}`}
      />
      <span className="relative z-10 w-14 text-center text-xs font-semibold text-slate-500 dark:text-white/40 transition-colors duration-200 select-none">
        Light
      </span>
      <span className="relative z-10 w-14 text-center text-xs font-semibold text-slate-800 dark:text-[#05080f] transition-colors duration-200 select-none">
        Dark
      </span>
    </button>
  );
}
