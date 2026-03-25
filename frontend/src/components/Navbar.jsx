import ThemeToggle from "./ThemeToggle";

export default function Navbar() {
  return (
    <nav className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <span className="text-lg font-semibold text-gray-900 dark:text-white">
          LoL Coach
        </span>
        <ThemeToggle />
      </div>
    </nav>
  );
}
