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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white text-center mb-2">
          League of Legends AI Coach
        </h1>
        <p className="text-gray-500 dark:text-gray-400 text-center mb-8 text-sm">
          Enter your Riot ID to get personalized coaching tips
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Game Name"
              value={gameName}
              onChange={(e) => setGameName(e.target.value)}
              className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-gray-400 dark:text-gray-500 font-medium">#</span>
            <input
              type="text"
              placeholder="Tag"
              value={tagLine}
              onChange={(e) => setTagLine(e.target.value)}
              className="w-24 px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && (
            <p className="text-red-500 dark:text-red-400 text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition-colors"
          >
            {loading ? "Looking up..." : "Analyze My Games"}
          </button>
        </form>
      </div>
    </div>
  );
}
