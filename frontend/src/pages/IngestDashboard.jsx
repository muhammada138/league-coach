import { useEffect, useState, useRef } from "react";
import { getIngestStatus, toggleIngest, getSyncStatus } from "../api/riot";

function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function IngestDashboard() {
  const [status, setStatus]   = useState(null);
  const [metaStatus, setMetaStatus] = useState({ active: false });
  const [toggling, setToggling] = useState(false);
  const [error, setError]     = useState("");
  const intervalRef = useRef(null);
  const [isAdmin, setIsAdmin] = useState(() => !!localStorage.getItem("admin_token"));
  const [autoResume, setAutoResume] = useState(() => localStorage.getItem("ingest_auto_resume") === "true");

  useEffect(() => {
    localStorage.setItem("ingest_auto_resume", autoResume);
  }, [autoResume]);

  useEffect(() => {
    if (!autoResume || !status?.is_paused) return;
    let timeout;
    const resetTimer = () => {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        if (status?.is_paused && isAdmin) {
          toggleIngest().then(data => {
            setStatus(data);
            if (!data.is_paused) {
              setHistory([{ processed: data.processed_count, time: Date.now() }]);
            }
          }).catch(() => {});
        }
      }, 30 * 60 * 1000);
    };
    window.addEventListener("mousemove", resetTimer);
    window.addEventListener("keydown", resetTimer);
    window.addEventListener("click", resetTimer);
    resetTimer();
    return () => {
      clearTimeout(timeout);
      window.removeEventListener("mousemove", resetTimer);
      window.removeEventListener("keydown", resetTimer);
      window.removeEventListener("click", resetTimer);
    };
  }, [autoResume, status?.is_paused, isAdmin]);

  const handleLogin = () => {
    const pass = prompt("Enter Admin API Key:");
    if (pass) {
      localStorage.setItem("admin_token", pass);
      setIsAdmin(true);
      fetchStatus();
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    setIsAdmin(false);
  };

  const fetchStatus = async () => {
    try {
      const [ingestData, metaData] = await Promise.all([
        getIngestStatus(),
        getSyncStatus()
      ]);
      setStatus(ingestData);
      setMetaStatus(metaData);
      setError("");
    } catch {
      setError("Could not reach backend.");
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  useEffect(() => {
    if (status && !status.is_paused) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = setInterval(fetchStatus, 10000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.is_paused]);

  const handleToggle = async () => {
    setToggling(true);
    try {
      const data = await toggleIngest();
      setStatus(data);
      if (!data.is_paused) {
        setHistory([{ processed: data.processed_count, time: Date.now() }]);
      }
    } catch {
      setError("Toggle failed.");
    } finally {
      setToggling(false);
    }
  };

  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem("ingest_history");
      if (saved) {
        const parsed = JSON.parse(saved);
        // Filter out old entries (> 5 mins) immediately
        const now = Date.now();
        return parsed.filter(h => now - h.time < 300000);
      }
    } catch (e) {}
    return [];
  });

  const processed   = status?.processed_count ?? 0;
  const target      = status?.total_target    ?? 50000;
  const isPaused    = status?.is_paused       ?? true;
  const pct         = target > 0 ? Math.min((processed / target) * 100, 100) : 0;
  const pctDisplay  = pct.toFixed(1);

  // Track history for delta calculation
  useEffect(() => {
    if (processed > 0) {
      setHistory(prev => {
        const now = Date.now();
        // If the last entry is the same as current processed count and 
        // it was less than 5 seconds ago, don't add to avoid spamming history
        const last = prev[prev.length - 1];
        if (last && last.processed === processed && now - last.time < 5000) {
          return prev;
        }

        const filtered = prev.filter(h => now - h.time < 300000);
        const next = [...filtered, { processed, time: now }];
        localStorage.setItem("ingest_history", JSON.stringify(next));
        return next;
      });
    }
  }, [processed]);

  // Calculate actual speed and ETA
  const { matchesPerMin, etaText } = (() => {
    if (isPaused || processed === 0) {
      return { matchesPerMin: 0, etaText: isPaused ? null : "Calculating speed..." };
    }

    if (history.length < 2) {
      const remaining = target - processed;
      const minsLeft = Math.round(remaining / 48);
      let text = minsLeft > 60 ? `~${(minsLeft / 60).toFixed(1)}h remaining` : `~${minsLeft}m remaining`;
      return { matchesPerMin: 48, etaText: text };
    }

    const first = history[0];
    const last  = history[history.length - 1];
    const deltaMatches = last.processed - first.processed;
    const deltaMins    = (last.time - first.time) / 60000;

    let mpm = deltaMatches / deltaMins;

    // Default to max (48) if we don't have enough time elapsed yet
    if (deltaMins < 0.25) { 
      mpm = 48; 
    }

    // If matches haven't moved, but we have recent history, keep showing the old speed
    // unless we've been stalled for a really long time (e.g. 5 minutes)
    if (deltaMatches <= 0 && deltaMins >= 0.25) {
      const lastMovementTime = last.time - first.time;
      if (lastMovementTime > 300000) { // 5 mins of zero progress
        mpm = 0; // We are running but not making progress, show 0 instead of faking max
      } else {
        // Fallback to calculating speed from a smaller window if possible
        mpm = Math.max(mpm, 0); 
      }
    }

    const remaining = target - processed;
    const minsLeft  = mpm > 0 ? Math.round(remaining / mpm) : Infinity;

    let text = "";
    if (minsLeft === Infinity) text = "Pending...";
    else if (minsLeft > 1440) text = `~${(minsLeft / 1440).toFixed(1)}d remaining`;
    else if (minsLeft > 60) text = `~${(minsLeft / 60).toFixed(1)}h remaining`;
    else text = `~${minsLeft}m remaining`;

    return { matchesPerMin: Math.round(mpm), etaText: text };
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
          <button 
            onClick={isAdmin ? handleLogout : handleLogin}
            className={`inline-flex items-center gap-2 text-[11px] font-bold tracking-widest uppercase
            px-4 py-1.5 rounded-full mb-5 border transition-all ${
              isAdmin 
                ? "text-emerald-400 border-emerald-400/25 bg-emerald-400/[0.06] hover:bg-rose-500/10 hover:border-rose-500/30 hover:text-rose-500" 
                : "text-[#c89b3c] border-[#c89b3c]/25 bg-[#c89b3c]/[0.06] hover:bg-[#c89b3c]/20"
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isAdmin ? "bg-emerald-400" : "bg-[#c89b3c]"}`} />
            {isAdmin ? "Logged In" : "Unlock Admin"}
          </button>
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

          {status?.rate_limited && (
            <div className="mb-6 flex items-center justify-between gap-3 px-5 py-4 rounded-2xl
              bg-amber-500/5 border border-amber-500/20 shadow-lg shadow-amber-900/10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center text-xl animate-pulse">
                  🛑
                </div>
                <div>
                  <div className="text-xs font-black text-amber-500 uppercase tracking-widest">
                    Riot Rate Limited
                  </div>
                  <div className="text-[10px] text-amber-400/60 font-medium">
                    The API is cooling down...
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-lg font-black text-amber-500 tabular-nums">
                  {status.rate_limit_remaining}s
                </span>
                <span className="text-[9px] text-amber-400/40 uppercase font-black tracking-tighter">
                  Remaining
                </span>
              </div>
            </div>
          )}

          {/* Status pill */}
          <div className="flex items-center justify-between mb-6">
            <span className="text-[11px] font-bold tracking-widest uppercase text-white/30">
              System Status
            </span>
            <div className="flex gap-2">
              {metaStatus.active && (
                <span className="inline-flex items-center gap-1.5 text-[10px] font-bold tracking-widest uppercase
                  px-3 py-1 rounded-full border border-blue-400/30 bg-blue-400/[0.08] text-blue-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                  Meta Tuning
                </span>
              )}
              {status === null ? (
                <span className="text-white/20 text-xs text-right leading-[22px]">Loading…</span>
              ) : (
                <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold tracking-widest uppercase
                  px-3 py-1 rounded-full border
                  ${isPaused
                    ? "text-amber-400 border-amber-400/30 bg-amber-400/[0.08]"
                    : "text-emerald-400 border-emerald-400/30 bg-emerald-400/[0.08]"
                  }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${isPaused ? "bg-amber-400" : "bg-emerald-400 animate-pulse"}`} />
                  {isPaused ? "Paused" : "Ingest Running"}
                </span>
              )}
            </div>
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
            <div className="flex flex-col">
              <span className="text-[#c89b3c] text-sm font-bold tabular-nums">
                {pctDisplay}%
              </span>
              {!isPaused && matchesPerMin > 0 && (
                <span className="text-white/20 text-[10px] font-medium uppercase tracking-wider mt-0.5">
                  {matchesPerMin} m/min
                </span>
              )}
            </div>
            {etaText && (
              <span className="text-white/25 text-xs text-right whitespace-pre-wrap">{etaText}</span>
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

          {/* Auto Resume Toggle */}
          <div className="mt-5 flex items-center justify-between px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
            <div className="flex flex-col">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Auto-Resume</span>
              <span className="text-[10px] text-white/40">Resumes after 30m of inactivity</span>
            </div>
            <button
              onClick={() => setAutoResume(!autoResume)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${autoResume ? 'bg-[#c89b3c]' : 'bg-white/10'}`}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${autoResume ? 'translate-x-5' : 'translate-x-1'}`}
              />
            </button>
          </div>
        </div>

        {/* Footer note */}
        <p className="text-center text-white/20 text-xs mt-6 leading-relaxed">
          Dev key: 100 req / 2m · Rank caching limits calls · 5 → 48 matches/min (warming up)
          <br />
          Cycling BRONZE → SILVER → GOLD → PLATINUM → EMERALD → DIAMOND → MASTER
        </p>

      </div>
    </div>
  );
}
