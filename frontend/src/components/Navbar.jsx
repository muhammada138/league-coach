import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";
import { getSummoner } from "../api/riot";
import SearchInput from "./SearchInput";
import useSearchHistory from "../hooks/useSearchHistory";

// ── Profile avatar ───────────────────────────────────────────────────────────
function ProfileAvatar({ profile }) {
  const [failed, setFailed] = useState(false);
  if (!profile.profileIconId || failed) {
    return (
      <span className="w-6 h-6 rounded-md bg-[#c89b3c]/10 border border-[#c89b3c]/20 text-[#c89b3c] text-[10px] font-black flex items-center justify-center flex-shrink-0">
        {profile.gameName?.charAt(0).toUpperCase()}
      </span>
    );
  }
  return (
    <img
      src={`https://ddragon.leagueoflegends.com/cdn/14.24.1/img/profileicon/${profile.profileIconId}.png`}
      alt=""
      className="w-6 h-6 rounded-md object-cover flex-shrink-0"
      onError={() => setFailed(true)}
    />
  );
}

// ── Navbar search bar ────────────────────────────────────────────────────────
function NavSearch() {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [region, setRegion] = useState(localStorage.getItem("lastRegion") || "na1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { saveToHistory } = useSearchHistory();

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
      
      // Clear inputs and navigate
      setGameName("");
      setTagLine("");
      
      navigate(
        `/player/${encodeURIComponent(data.gameName)}/${encodeURIComponent(finalTag.trim())}`,
        { state: { puuid: data.puuid, region: finalRegion } }
      );
    } catch (err) {
      setError(err.response?.status === 404 ? "Not found" : "Error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="hidden sm:block ml-4">
      <SearchInput 
        navbar
        region={region}
        setRegion={setRegion}
        gameName={gameName}
        setGameName={setGameName}
        tagLine={tagLine}
        setTagLine={setTagLine}
        onSubmit={handleSearch}
        loading={loading}
        error={error}
        placeholder="Riot ID#TAG"
      />
    </div>
  );
}

// ── Saved profiles dropdown ──────────────────────────────────────────────────
function SavedDropdown() {
  const [open, setOpen] = useState(false);
  const { saved, toggleSaved } = useSearchHistory();
  const [loadingId, setLoadingId] = useState(null);
  const wrapperRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e) => {
      if (!wrapperRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  const handleNavigate = async (p) => {
    setLoadingId(p.puuid);
    try {
      const region = p.region || localStorage.getItem("lastRegion") || "na1";
      const data = await getSummoner(p.gameName, p.tagLine, region);
      setOpen(false);
      navigate(
        `/player/${encodeURIComponent(data.gameName)}/${encodeURIComponent(p.tagLine)}`,
        { state: { puuid: data.puuid, region } }
      );
    } catch {
      setOpen(false);
      const region = p.region || localStorage.getItem("lastRegion") || "na1";
      navigate(
        `/player/${encodeURIComponent(p.gameName)}/${encodeURIComponent(p.tagLine)}`,
        { state: { puuid: p.puuid, region } }
      );
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 h-9 px-3 rounded-xl border text-[11px] font-bold tracking-tight transition-all duration-200
          ${open
            ? "bg-[#c89b3c]/10 border-[#c89b3c]/40 text-[#c89b3c] shadow-lg shadow-[#c89b3c]/5"
            : "bg-white dark:bg-white/[0.04] border-slate-200 dark:border-white/10 text-slate-500 dark:text-white/40 hover:text-[#c89b3c] hover:border-[#c89b3c]/30"
          }`}
      >
        <svg className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 1.5l1.75 3.55 3.92.57-2.84 2.77.67 3.9L8 10.35l-3.5 1.84.67-3.9L2.33 5.62l3.92-.57L8 1.5z" />
        </svg>
        <span className="hidden md:inline uppercase tracking-widest text-[9px]">Saved</span>
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-64 z-50
          bg-white dark:bg-[#0d111a]
          border border-slate-200 dark:border-white/[0.08]
          rounded-2xl shadow-2xl shadow-black/60
          overflow-hidden animate-fadeIn backdrop-blur-xl">

          <div className="px-5 py-3 border-b border-slate-100 dark:border-white/[0.04] bg-slate-50/50 dark:bg-white/[0.02]">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 dark:text-white/20">
              Saved Profiles
            </span>
          </div>

          {saved.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <p className="text-xs text-slate-400 dark:text-white/20 mb-1">No saved profiles yet</p>
              <p className="text-[10px] text-slate-300 dark:text-white/10 italic">Click the star on a profile to save it</p>
            </div>
          ) : (
            <div className="py-1 max-h-72 overflow-y-auto custom-scrollbar">
              {saved.map((p) => (
                <div
                  key={p.puuid}
                  onClick={() => handleNavigate(p)}
                  className="group flex items-center gap-3 px-4 py-3 cursor-pointer
                    hover:bg-[#c89b3c]/5 transition-colors border-b border-transparent hover:border-[#c89b3c]/10"
                >
                  <div className="relative flex-shrink-0">
                    <ProfileAvatar profile={p} />
                    {loadingId === p.puuid && (
                      <div className="absolute inset-0 flex items-center justify-center bg-white/60 dark:bg-black/60 rounded-md">
                        <span className="w-3 h-3 rounded-full border-[1.5px] border-white/30 border-t-[#c89b3c] animate-spin block" />
                      </div>
                    )}
                  </div>

                  <div className="flex-1 min-w-0 flex flex-col">
                    <span className="text-xs font-bold text-slate-800 dark:text-white/80 truncate leading-tight">
                      {p.gameName}
                      <span className="text-slate-400 dark:text-white/20 font-medium ml-0.5">#{p.tagLine}</span>
                    </span>
                    {p.region && (
                      <span className="text-[9px] font-black text-[#c89b3c]/60 uppercase tracking-tighter">
                        {p.region}
                      </span>
                    )}
                  </div>

                  <button
                    onClick={(e) => { e.stopPropagation(); toggleSaved(p); }}
                    className="flex-shrink-0 w-6 h-6 rounded-lg flex items-center justify-center
                      text-red-400/40 hover:text-red-500 hover:bg-red-500/10
                      opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M12 4L4 12M4 4l8 8" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Navbar ───────────────────────────────────────────────────────────────────
export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50
      bg-white/80 dark:bg-[#05080f]/80
      backdrop-blur-xl
      border-b border-slate-200/60 dark:border-white/[0.04]
      transition-all duration-300 shadow-sm">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo Section (Left) */}
        <Link to="/" className="flex items-center gap-2.5 group flex-shrink-0">
          <img 
            src="/logo.png" 
            alt="Rift IQ" 
            className="w-8 h-8 rounded-lg shadow-lg shadow-[#c89b3c]/10 group-hover:scale-105 transition-transform"
          />
          <span className="text-lg font-black tracking-tighter text-slate-900 dark:text-white/90">RIFT IQ</span>
        </Link>

        {/* Right Actions Cluster (Search + Saved + Theme) */}
        <div className="flex items-center gap-3 ml-auto">
          <NavSearch />
          <div className="flex items-center gap-2.5">
            <SavedDropdown />
            <div className="w-px h-4 bg-slate-200 dark:bg-white/10 mx-1 hidden sm:block" />
            <ThemeToggle />
          </div>
        </div>
      </div>
    </nav>
  );
}
