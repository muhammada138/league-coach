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
    <div className="min-h-screen bg-[#05080f] flex items-center justify-center px-4 relative overflow-hidden">
      {/* Background glow blobs */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#c89b3c]/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-[400px] h-[400px] bg-blue-900/10 rounded-full blur-[100px] pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Badge */}
        <div className="flex justify-center mb-6">
          <span className="text-xs font-semibold tracking-widest uppercase text-[#c89b3c] border border-[#c89b3c]/30 bg-[#c89b3c]/5 px-3 py-1 rounded-full">
            AI-Powered Coaching
          </span>
        </div>

        {/* Heading */}
        <h1 className="text-4xl font-bold text-white text-center mb-3 leading-tight tracking-tight">
          League of Legends
          <br />
          <span className="text-[#c89b3c]">AI Coach</span>
        </h1>
        <p className="text-white/40 text-center mb-10 text-sm leading-relaxed">
          Enter your Riot ID to get personalized coaching
          <br />
          based on your last 5 ranked games
        </p>

        {/* Card */}
        <div className="bg-white/[0.03] border border-white/8 rounded-2xl p-8 backdrop-blur-sm shadow-2xl shadow-black/40">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Input row */}
            <div className="flex items-stretch gap-0 rounded-xl overflow-hidden border border-white/10 focus-within:border-[#c89b3c]/50 transition-colors bg-white/[0.04]">
              <input
                type="text"
                placeholder="Game Name"
                value={gameName}
                onChange={(e) => setGameName(e.target.value)}
                className="flex-1 px-4 py-3 bg-transparent text-white placeholder-white/25 focus:outline-none text-sm"
              />
              <div className="flex items-center px-3 text-white/20 font-medium text-base select-none border-l border-white/10">
                #
              </div>
              <input
                type="text"
                placeholder="TAG"
                value={tagLine}
                onChange={(e) => setTagLine(e.target.value)}
                className="w-20 px-3 py-3 bg-transparent text-white placeholder-white/25 focus:outline-none text-sm"
              />
            </div>

            {/* Error */}
            {error && (
              <p className="text-red-400/90 text-xs flex items-center gap-1.5">
                <span className="inline-block w-1 h-1 rounded-full bg-red-400 flex-shrink-0" />
                {error}
              </p>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl font-semibold text-sm tracking-wide transition-all
                bg-[#c89b3c] hover:bg-[#d4a94a] active:scale-[0.98]
                disabled:opacity-40 disabled:cursor-not-allowed
                text-[#05080f] shadow-lg shadow-[#c89b3c]/20"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-[#05080f]/30 border-t-[#05080f] rounded-full animate-spin" />
                  Looking up...
                </span>
              ) : (
                "Analyze My Games"
              )}
            </button>
          </form>
        </div>

        {/* Footer note */}
        <p className="text-center text-white/20 text-xs mt-5">
          Ranked Solo/Duo · Last 5 games
        </p>
      </div>
    </div>
  );
}
