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

export default function Home() {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine]   = useState("");
  const [region, setRegion]     = useState(localStorage.getItem("lastRegion") || "na1");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  
  const { saveToHistory } = useSearchHistory();
  const navigate = useNavigate();

  const handleSearch = async () => {
    if (!gameName.trim() || !tagLine.trim()) return;
    
    setLoading(true);
    setError("");
    try {
      const data = await getSummoner(gameName.trim(), tagLine.trim(), region);
      saveToHistory(`${gameName.trim()}#${tagLine.trim()}`);
      localStorage.setItem("lastRegion", region);
      navigate(
        `/player/${encodeURIComponent(data.gameName)}/${encodeURIComponent(tagLine.trim())}`,
        { state: { puuid: data.puuid, gameCount: 20, region } }
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
    <div className="min-h-screen flex flex-col items-center justify-center px-4 pt-14 pb-20 relative overflow-hidden">
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
