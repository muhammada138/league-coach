import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSummoner } from "../api/riot";

// subtle dot-grid SVG background
const DOT_GRID = `url("data:image/svg+xml,%3Csvg width='28' height='28' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='1' cy='1' r='1' fill='%23c89b3c'/%3E%3C/svg%3E")`;

const HOW_IT_WORKS = [
  {
    n: "01",
    title: "Enter your Riot ID",
    desc: "Type your game name and tag — any region works.",
  },
  {
    n: "02",
    title: "We crunch the games",
    desc: "Your last 5 ranked games are pulled and compared against each lobby's average.",
  },
  {
    n: "03",
    title: "Get targeted coaching",
    desc: "An AI model turns the numbers into 3–5 specific, impact-ranked tips.",
  },
];

export default function Home() {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine]   = useState("");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!gameName.trim() || !tagLine.trim()) return;

    setLoading(true);
    setError("");

    try {
      const data = await getSummoner(gameName.trim(), tagLine.trim());
      navigate(
        `/player/${encodeURIComponent(data.gameName)}/${encodeURIComponent(tagLine.trim())}`,
        { state: { puuid: data.puuid } }
      );
    } catch (err) {
      const status = err.response?.status;
      setError(
        status === 404
          ? "Summoner not found. Check your Riot ID and tag."
          : "Something went wrong. Try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 pt-14 pb-20 relative overflow-hidden">

      {/* ── Background layers ─────────────────────────────────────────────── */}

      {/* dot grid — light mode subtle, slightly more visible in dark */}
      <div
        className="absolute inset-0 opacity-[0.025] dark:opacity-[0.045] pointer-events-none"
        style={{ backgroundImage: DOT_GRID, backgroundSize: "28px 28px" }}
      />

      {/* dark-mode color blobs */}
      <div className="hidden dark:block absolute top-[28%] left-1/2 -translate-x-1/2 -translate-y-1/2
        w-[800px] h-[600px] rounded-full pointer-events-none
        bg-[#c89b3c]/[0.055] blur-[160px]" />
      <div className="hidden dark:block absolute bottom-0 left-[15%]
        w-[460px] h-[460px] rounded-full pointer-events-none
        bg-blue-950/40 blur-[120px]" />
      <div className="hidden dark:block absolute bottom-10 right-[10%]
        w-[320px] h-[320px] rounded-full pointer-events-none
        bg-[#c89b3c]/[0.025] blur-[100px]" />

      {/* light-mode glow */}
      <div className="dark:hidden absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
        w-[600px] h-[400px] rounded-full pointer-events-none
        bg-[#c89b3c]/[0.07] blur-[100px]" />

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <div className="relative w-full max-w-md animate-fadeUp">

        {/* Badge */}
        <div className="flex justify-center mb-7">
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold tracking-widest uppercase
            text-[#c89b3c] border border-[#c89b3c]/30 bg-[#c89b3c]/[0.06] px-4 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c89b3c] animate-pulse" />
            AI-Powered Coaching
          </span>
        </div>

        {/* Heading */}
        <div className="text-center mb-10">
          <h1 className="text-[2.75rem] font-extrabold tracking-tight leading-[1.1] mb-3">
            <span className="text-slate-900 dark:text-white">Stop guessing.</span>
            <br />
            <span className="text-[#c89b3c]">Start climbing.</span>
          </h1>
          <p className="text-slate-500 dark:text-white/35 text-sm leading-relaxed max-w-sm mx-auto">
            Enter your Riot ID and get coaching built from your actual numbers —
            compared against every player in your last 5 ranked lobbies.
          </p>
        </div>

        {/* Card */}
        <div className="
          bg-white dark:bg-white/[0.03]
          border border-slate-200 dark:border-white/[0.08]
          rounded-2xl p-8
          shadow-2xl shadow-slate-200/80 dark:shadow-black/60
          backdrop-blur-sm
          ring-1 ring-black/[0.02] dark:ring-white/[0.03]
          transition-colors duration-300
        ">
          <form onSubmit={handleSubmit} className="space-y-3">

            <label className="block text-[11px] font-bold tracking-widest uppercase text-slate-400 dark:text-white/30 mb-2">
              Riot ID
            </label>

            {/* Input row */}
            <div className="flex items-stretch rounded-xl overflow-hidden
              border border-slate-200 dark:border-white/10
              focus-within:border-[#c89b3c]/60 dark:focus-within:border-[#c89b3c]/50
              focus-within:ring-2 focus-within:ring-[#c89b3c]/10
              bg-slate-50 dark:bg-white/[0.04]
              transition-all duration-200 shadow-inner">
              <input
                type="text"
                placeholder="Game Name"
                value={gameName}
                onChange={(e) => setGameName(e.target.value)}
                className="flex-1 px-4 py-3.5 bg-transparent
                  text-slate-900 dark:text-white
                  placeholder-slate-400 dark:placeholder-white/20
                  focus:outline-none text-sm"
              />
              <div className="flex items-center px-3 text-slate-300 dark:text-white/15 font-bold text-sm select-none border-l border-slate-200 dark:border-white/10">
                #
              </div>
              <input
                type="text"
                placeholder="TAG"
                value={tagLine}
                onChange={(e) => setTagLine(e.target.value)}
                className="w-20 px-3 py-3.5 bg-transparent
                  text-slate-900 dark:text-white
                  placeholder-slate-400 dark:placeholder-white/20
                  focus:outline-none text-sm"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                <p className="text-red-600 dark:text-red-400 text-xs">{error}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 mt-1 rounded-xl font-bold text-sm tracking-wide
                bg-[#c89b3c] hover:bg-[#d4a94a] active:scale-[0.985]
                disabled:opacity-40 disabled:cursor-not-allowed
                text-[#1a1000]
                shadow-lg shadow-[#c89b3c]/30 hover:shadow-[#c89b3c]/50
                transition-all duration-200"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-[#1a1000]/20 border-t-[#1a1000]/70 rounded-full animate-spin" />
                  Analyzing...
                </span>
              ) : (
                "Analyze My Games →"
              )}
            </button>

          </form>
        </div>

        {/* How it works */}
        <div className="mt-10">
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-slate-200 dark:bg-white/[0.06]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">
              How it works
            </span>
            <div className="flex-1 h-px bg-slate-200 dark:bg-white/[0.06]" />
          </div>

          <div className="space-y-3">
            {HOW_IT_WORKS.map(({ n, title, desc }) => (
              <div
                key={n}
                className="flex items-start gap-4 p-4
                  bg-white dark:bg-white/[0.02]
                  border border-slate-100 dark:border-white/[0.05]
                  rounded-xl
                  hover:border-slate-200 dark:hover:border-white/[0.08]
                  transition-colors duration-150"
              >
                <span className="flex-shrink-0 text-[11px] font-black text-[#c89b3c]/60 tabular-nums mt-0.5">
                  {n}
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white/80 leading-tight mb-0.5">
                    {title}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-white/30 leading-relaxed">
                    {desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer note */}
        <div className="flex items-center justify-center gap-5 mt-8">
          {["Solo/Duo Ranked", "All Regions", "Groq AI"].map((tag) => (
            <span key={tag} className="text-[11px] text-slate-400 dark:text-white/20 font-medium">
              {tag}
            </span>
          ))}
        </div>

      </div>
    </div>
  );
}
