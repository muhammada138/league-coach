import ThemeToggle from "./ThemeToggle";

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-[#05080f]/80 backdrop-blur-md border-b border-white/5">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <span className="text-sm font-semibold tracking-widest uppercase text-[#c89b3c]">
          LoL Coach
        </span>
        <ThemeToggle />
      </div>
    </nav>
  );
}
