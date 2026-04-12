import { useEffect, useState, useRef } from "react";
import { getIngestStatus, toggleIngest } from "../api/riot";

function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function IngestDashboard() {
  const [status, setStatus]   = useState(null);
  const [toggling, setToggling] = useState(false);
  const [error, setError]     = useState("");
  const intervalRef = useRef(null);

  const fetchStatus = async () => {
    try {
      const data = await getIngestStatus();
      setStatus(data);
      setError("");
    } catch {
      setError("Could not reach backend.");
    }
  };

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 3000);
    return () => clearInterval(intervalRef.current);
  }, []);

  const handleToggle = async () => {
    setToggling(true);
    try {
      const data = await toggleIngest();
      setStatus(data);
    } catch {
      setError("Toggle failed.");
    } finally {
      setToggling(false);
    }
  };

  const processed   = status?.processed_count ?? 0;
  const target      = status?.total_target    ?? 50000;
  const isPaused    = status?.is_paused       ?? true;
  const pct         = target > 0 ? Math.min((processed / target) * 100, 100) : 0;
  const pctDisplay  = pct.toFixed(1);

  // ETA rough estimate — shown only when running and some progress exists
  const etaText = (() => {
    if (isPaused || processed === 0) return null;
    // ~89 calls per ladder page → ~80 new matches in ~111s ≈ 43 matches/min
    const remaining = target - processed;
    const minsLeft  = Math.round(remaining / 43);
    if (minsLeft > 1440) return `~${Math.round(minsLeft / 1440)}d remaining`;
    if (minsLeft > 60)   return `~${Math.round(minsLeft / 60)}h remaining`;
    return `~${minsLeft}m remaining`;
  })();

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 bg-[#05080f]">

      {/* Ambient glow */}
      <div className="fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2
        w-[700px] h-[500px] rounded-full pointer-events-none
        bg-[#c89b3c]/[0.04] blur-[160px]" />

      <div className="relative w-full max-w-lg">

        {/* Header */}
        <div className="mb-10 text-center">
          <span className="inline-flex items-center gap-2 text-[11px] font-bold tracking-widest uppercase
            text-[#c89b3c] border border-[#c89b3c]/25 bg-[#c89b3c]/[0.06] px-4 py-1.5 rounded-full mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c89b3c]" />
            Admin
          </span>
          <h1 className="text-2xl font-extrabold tracking-tight text-white mt-3">
            ML Training Ingestion
          </h1>
          <p className="text-white/30 text-sm mt-2">
            Accumulating real match data to retrain the win predictor.
          </p>
        </div>

        {/* Main card */}
        <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-8
          shadow-2xl shadow-black/60 backdrop-blur-sm">

          {error && (
            <div className="mb-6 flex items-center gap-2 px-4 py-3 rounded-xl
              bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Status pill */}
          <div className="flex items-center justify-between mb-6">
            <span className="text-[11px] font-bold tracking-widest uppercase text-white/30">
              Status
            </span>
            {status === null ? (
              <span className="text-white/20 text-xs">Loading…</span>
            ) : (
              <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold tracking-widest uppercase
                px-3 py-1 rounded-full border
                ${isPaused
                  ? "text-amber-400 border-amber-400/30 bg-amber-400/[0.08]"
                  : "text-emerald-400 border-emerald-400/30 bg-emerald-400/[0.08]"
                }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${isPaused ? "bg-amber-400" : "bg-emerald-400 animate-pulse"}`} />
                {isPaused ? "Paused" : "Running"}
              </span>
            )}
          </div>

          {/* Big counter */}
          <div className="text-center mb-6">
            <div className="text-[2.6rem] font-black tabular-nums tracking-tight text-white leading-none">
              {fmt(processed)}
            </div>
            <div className="text-white/30 text-sm mt-1">
              of {fmt(target)} matches
            </div>
          </div>

          {/* Progress bar */}
          <div className="relative mb-2">
            <div className="h-3 w-full rounded-full bg-white/[0.06] overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${pct}%`,
                  background: pct >= 100
                    ? "linear-gradient(90deg, #22c55e, #16a34a)"
                    : "linear-gradient(90deg, #c89b3c, #e8b84b)",
                  boxShadow: pct > 0 ? "0 0 12px rgba(200,155,60,0.4)" : "none",
                }}
              />
            </div>
          </div>

          {/* Pct + ETA row */}
          <div className="flex items-center justify-between mb-8">
            <span className="text-[#c89b3c] text-sm font-bold tabular-nums">
              {pctDisplay}%
            </span>
            {etaText && (
              <span className="text-white/25 text-xs">{etaText}</span>
            )}
          </div>

          {/* Play / Pause button */}
          <button
            onClick={handleToggle}
            disabled={toggling || status === null}
            className={`w-full py-4 rounded-xl font-bold text-sm tracking-wide flex items-center justify-center gap-3
              transition-all duration-200 active:scale-[0.985]
              disabled:opacity-40 disabled:cursor-not-allowed
              ${isPaused
                ? "bg-[#c89b3c] hover:bg-[#d4a94a] text-[#1a1000] shadow-lg shadow-[#c89b3c]/25 hover:shadow-[#c89b3c]/45"
                : "bg-white/[0.06] hover:bg-white/[0.10] border border-white/[0.10] text-white"
              }`}
          >
            {toggling ? (
              <span className="w-4 h-4 border-2 border-current/30 border-t-current rounded-full animate-spin" />
            ) : isPaused ? (
              <>
                {/* Play icon */}
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M3 2.5l10 5.5-10 5.5V2.5z" />
                </svg>
                Resume Ingestion
              </>
            ) : (
              <>
                {/* Pause icon */}
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                  <rect x="3" y="2" width="4" height="12" rx="1" />
                  <rect x="9" y="2" width="4" height="12" rx="1" />
                </svg>
                Pause Ingestion
              </>
            )}
          </button>
        </div>

        {/* Footer note */}
        <p className="text-center text-white/20 text-xs mt-6 leading-relaxed">
          Dev key: ~48 req/min · Semaphore(1) · 1.25s between calls · ~43 matches/min
          <br />
          Cycling BRONZE → SILVER → GOLD → PLATINUM → EMERALD → DIAMOND → MASTER
        </p>

      </div>
    </div>
  );
}
