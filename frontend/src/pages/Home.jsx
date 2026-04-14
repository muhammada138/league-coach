import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { getSummoner } from "../api/riot";
import SearchInput from "../components/SearchInput";
import useSearchHistory from "../hooks/useSearchHistory";

const DOT_GRID = `url("data:image/svg+xml,%3Csvg width='28' height='28' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='1' cy='1' r='1' fill='%23c89b3c'/%3E%3C/svg%3E")`;

const HOW_IT_WORKS = [
  {
    n: "01",
    title: "Enter your Riot ID",
    desc: "Type your game name and tag. Any region works.",
  },
  {
    n: "02",
    title: "We crunch the games",
    desc: "Your recent ranked games are pulled and compared against each lobby's average.",
  },
  {
    n: "03",
    title: "Get targeted coaching",
    desc: "An AI model turns the numbers into 3–5 specific, impact-ranked tips.",
  },
];

function QuickFavorites() {
  const { saved, toggleSaved } = useSearchHistory();
  const navigate = useNavigate();

  if (!saved || saved.length === 0) return null;

  return (
    <div className="w-full max-w-2xl mt-4 flex flex-wrap justify-center gap-2 animate-fadeIn">
      {saved.map((p) => {
        const region = p.region || localStorage.getItem("lastRegion") || "na1";
        return (
          <div
            key={`${p.gameName}#${p.tagLine}`}
            className="group flex items-center gap-2 px-3 py-1.5 bg-white/50 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-full hover:border-[#c89b3c]/40 hover:bg-[#c89b3c]/[0.03] transition-all cursor-pointer shadow-sm"
            onClick={() => navigate(`/player/${encodeURIComponent(p.gameName)}/${encodeURIComponent(p.tagLine)}`, { state: { puuid: p.puuid, region } })}
          >
            <div className="w-5 h-5 rounded-md bg-[#c89b3c]/10 border border-[#c89b3c]/20 flex items-center justify-center text-[#c89b3c] text-[8px] font-black uppercase">
              {p.gameName.charAt(0)}
            </div>
            <span className="text-[11px] font-bold text-slate-700 dark:text-white/70 truncate max-w-[100px]">
              {p.gameName}
              <span className="text-slate-400 dark:text-white/20 font-medium ml-0.5">#{p.tagLine}</span>
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); toggleSaved(p); }}
              className="w-4 h-4 rounded-full flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-red-500/10 transition-colors"
              title="Remove from Favorites"
            >
              <svg className="w-2.5 h-2.5" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M9 3L3 9M3 3L9 9" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default function Home() {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine]   = useState("");
  const [region, setRegion]     = useState(localStorage.getItem("lastRegion") || "na1");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  
  const { saveToHistory } = useSearchHistory();
  const navigate = useNavigate();

  const handleSearch = async (suggestion) => {
    const finalName = suggestion?.gameName || gameName;
    const finalTag  = suggestion?.tagLine || tagLine;
    const finalRegion = suggestion?.region || region;

    if (!finalName.trim() || !finalTag.trim()) return;
    
    setLoading(true);
    setError("");
    try {
      const data = await getSummoner(finalName.trim(), finalTag.trim(), finalRegion);
      saveToHistory({ gameName: finalName.trim(), tagLine: finalTag.trim(), region: finalRegion });
      localStorage.setItem("lastRegion", finalRegion);
      navigate(
        `/player/${encodeURIComponent(data.gameName)}/${encodeURIComponent(finalTag.trim())}`,
        { state: { puuid: data.puuid, gameCount: 20, region: finalRegion } }
      );
    } catch (err) {
      setError(
        err.response?.status === 404
          ? "Summoner not found. Check your Riot ID and tag."
          : "Something went wrong. Try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 pt-24 pb-20 relative overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 opacity-[0.025] dark:opacity-[0.045] pointer-events-none" style={{ backgroundImage: DOT_GRID, backgroundSize: "28px 28px" }} />
      <div className="hidden dark:block absolute top-[28%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] rounded-full pointer-events-none bg-[#c89b3c]/[0.055] blur-[160px]" />
      
      <div className="relative w-full max-w-2xl animate-fadeUp flex flex-col items-center">
        {/* Badge */}
        <div className="flex justify-center mb-8">
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold tracking-widest uppercase
            text-[#c89b3c] border border-[#c89b3c]/30 bg-[#c89b3c]/[0.06] px-4 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c89b3c] animate-pulse" />
            AI-Powered Coaching
          </span>
        </div>

        {/* Hero */}
        <div className="text-center mb-12">
          <h1 className="text-[3.5rem] md:text-[4rem] font-black tracking-tighter leading-[1.05] mb-5">
            <span className="text-slate-900 dark:text-white">Stop guessing.</span>
            <br />
            <span className="text-[#c89b3c]">Start climbing.</span>
          </h1>
          <p className="text-slate-500 dark:text-white/35 text-base leading-relaxed max-w-md mx-auto">
            Get personalized coaching built from your actual gameplay, 
            benchmarked against every player in your last 10 lobbies.
          </p>
        </div>

        {/* Main Search Bar (The "DeepLol" style) */}
        <SearchInput 
          region={region}
          setRegion={setRegion}
          gameName={gameName}
          setGameName={setGameName}
          tagLine={tagLine}
          setTagLine={setTagLine}
          onSubmit={handleSearch}
          loading={loading}
          error={error}
        />

        {/* Quick Access Favorites Bar */}
        <QuickFavorites />

        {/* Secondary section: How it works */}
        <div className="w-full max-w-lg mt-16">
          <div className="flex items-center gap-3 mb-8">
            <div className="flex-1 h-px bg-slate-200 dark:bg-white/[0.06]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">
              How it works
            </span>
            <div className="flex-1 h-px bg-slate-200 dark:bg-white/[0.06]" />
          </div>

          <div className="grid grid-cols-1 gap-4">
            {HOW_IT_WORKS.map(({ n, title, desc }) => (
              <div key={n} className="group flex items-start gap-4 p-5 bg-white dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05] rounded-2xl hover:border-slate-200 dark:hover:border-white/[0.1] transition-all duration-300">
                <span className="flex-shrink-0 text-sm font-black text-[#c89b3c]/40 group-hover:text-[#c89b3c] transition-colors tabular-nums mt-0.5">
                  {n}
                </span>
                <div>
                  <p className="text-sm font-bold text-slate-800 dark:text-white/80 leading-tight mb-1">
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

        {/* Footer Tags */}
        <div className="flex items-center justify-center gap-8 mt-12 pt-8 border-t border-slate-100 dark:border-white/[0.05] w-full max-w-md">
          <Link to="/terms" className="text-[10px] uppercase font-bold tracking-widest text-slate-400 dark:text-white/20 hover:text-[#c89b3c] transition-colors">Terms</Link>
          <Link to="/privacy" className="text-[10px] uppercase font-bold tracking-widest text-slate-400 dark:text-white/20 hover:text-[#c89b3c] transition-colors">Privacy</Link>
          <span className="text-[10px] uppercase font-bold tracking-widest text-slate-400 dark:text-white/20">© 2026 Rift IQ</span>
        </div>
      </div>
    </div>
  );
}
