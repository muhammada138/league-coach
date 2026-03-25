import ThemeToggle from "./ThemeToggle";

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50
      bg-slate-50/80 dark:bg-[#05080f]/80
      backdrop-blur-md
      border-b border-slate-200/80 dark:border-white/5
      transition-colors duration-300">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <span className="text-sm font-bold tracking-widest uppercase text-[#c89b3c]">
          LoL Coach
        </span>
        <ThemeToggle />
      </div>
    </nav>
  );
}
