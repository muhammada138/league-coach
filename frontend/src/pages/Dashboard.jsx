import { useLocation } from "react-router-dom";

export default function Dashboard() {
  const { state } = useLocation();

  return (
    <div className="min-h-screen flex items-center justify-center px-4 pt-14">
      <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl shadow-xl shadow-slate-200/80 dark:shadow-black/50 p-10 text-center max-w-sm w-full transition-colors duration-300">
        <h1 className="text-xl font-bold text-slate-900 dark:text-white mb-4">
          Dashboard coming soon
        </h1>
        {state && (
          <div className="text-xs text-slate-400 dark:text-white/30 space-y-1.5 text-left bg-slate-50 dark:bg-white/[0.03] rounded-lg p-4 font-mono border border-slate-100 dark:border-white/5">
            <p><span className="text-[#c89b3c]">gameName</span>: {state.gameName}</p>
            <p><span className="text-[#c89b3c]">puuid</span>: {state.puuid}</p>
          </div>
        )}
      </div>
    </div>
  );
}
