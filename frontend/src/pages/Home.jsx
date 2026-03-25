import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSummoner } from "../api/riot";

export default function Home() {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!gameName.trim() || !tagLine.trim()) return;

    setLoading(true);
    setError("");

    try {
      const data = await getSummoner(gameName.trim(), tagLine.trim());
      navigate("/dashboard", {
        state: { puuid: data.puuid, gameName: data.gameName },
      });
    } catch (err) {
      const status = err.response?.status;
      if (status === 404) {
        setError("Summoner not found. Check your Riot ID and tag.");
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 pt-14 relative overflow-hidden">

      {/* Dark mode glow blobs */}
      <div className="hidden dark:block absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] bg-[#c89b3c]/[0.04] rounded-full blur-[140px] pointer-events-none" />
      <div className="hidden dark:block absolute bottom-0 left-1/4 w-[500px] h-[500px] bg-blue-950/30 rounded-full blur-[120px] pointer-events-none" />

      {/* Light mode subtle glow */}
      <div className="dark:hidden absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-[#c89b3c]/[0.06] rounded-full blur-[100px] pointer-events-none" />

      <div className="relative w-full max-w-md">

        {/* Badge */}
        <div className="flex justify-center mb-6">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase
            text-[#c89b3c] border border-[#c89b3c]/30 bg-[#c89b3c]/5 px-4 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c89b3c] animate-pulse" />
            AI-Powered Coaching
          </span>
        </div>

        {/* Heading */}
        <h1 className="text-[2.6rem] font-extrabold text-slate-900 dark:text-white text-center mb-3 leading-[1.15] tracking-tight">
          League of Legends
          <br />
          <span className="text-[#c89b3c]">AI Coach</span>
        </h1>
        <p className="text-slate-500 dark:text-white/35 text-center mb-10 text-sm leading-relaxed">
          Enter your Riot ID · Get coaching based on
          <br />
          your last 5 ranked games
        </p>

        {/* Card */}
        <div className="
          bg-white dark:bg-white/[0.03]
          border border-slate-200 dark:border-white/[0.07]
          rounded-2xl p-8
          shadow-xl shadow-slate-200/80 dark:shadow-black/50
          backdrop-blur-sm
          transition-colors duration-300
        ">
          <form onSubmit={handleSubmit} className="space-y-3">

            {/* Label */}
            <label className="block text-xs font-semibold tracking-widest uppercase text-slate-400 dark:text-white/30 mb-2">
              Riot ID
            </label>

            {/* Input row */}
            <div className="flex items-stretch rounded-xl overflow-hidden
              border border-slate-200 dark:border-white/10
              focus-within:border-[#c89b3c]/60 dark:focus-within:border-[#c89b3c]/50
              bg-slate-50 dark:bg-white/[0.04]
              transition-colors duration-200 shadow-inner">
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
                shadow-lg shadow-[#c89b3c]/25 hover:shadow-[#c89b3c]/40
                transition-all duration-200"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-[#1a1000]/20 border-t-[#1a1000]/70 rounded-full animate-spin" />
                  Looking up...
                </span>
              ) : (
                "Analyze My Games →"
              )}
            </button>
          </form>
        </div>

        {/* Footer note */}
        <div className="flex items-center justify-center gap-4 mt-6">
          {["Solo/Duo Ranked", "Last 5 Games", "Groq AI"].map((tag) => (
            <span key={tag} className="text-[11px] text-slate-400 dark:text-white/20 font-medium">
              {tag}
            </span>
          ))}
        </div>

      </div>
    </div>
  );
}
