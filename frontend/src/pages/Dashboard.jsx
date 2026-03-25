import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getProfile, analyzeSummoner } from "../api/riot";

const GOLD = "#c89b3c";

const TIER_COLORS = {
  IRON: "text-slate-400",
  BRONZE: "text-orange-700",
  SILVER: "text-slate-300",
  GOLD: "text-yellow-500",
  PLATINUM: "text-emerald-400",
  EMERALD: "text-emerald-500",
  DIAMOND: "text-blue-400",
  MASTER: "text-purple-400",
  GRANDMASTER: "text-red-400",
  CHALLENGER: "text-sky-300",
  UNRANKED: "text-slate-400",
};

function card(extra = "") {
  return `bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl shadow-sm dark:shadow-black/40 transition-colors duration-300 ${extra}`;
}

// ── Loading screen ──────────────────────────────────────────────────────────
function LoadingScreen() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-5 pt-14">
      <div className="relative w-14 h-14">
        <div className="absolute inset-0 rounded-full border-2 border-[#c89b3c]/20" />
        <div className="absolute inset-0 rounded-full border-2 border-t-[#c89b3c] animate-spin" />
      </div>
      <p className="text-slate-500 dark:text-white/40 text-sm font-medium tracking-wide animate-pulse">
        Analyzing your last 5 games...
      </p>
    </div>
  );
}

// ── Error screen ─────────────────────────────────────────────────────────────
function ErrorScreen({ message, onRetry }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 pt-14 px-4">
      <p className="text-red-500 dark:text-red-400 text-sm">{message}</p>
      <button onClick={onRetry} className="text-sm font-semibold text-[#c89b3c] hover:underline">
        ← Search Again
      </button>
    </div>
  );
}

// ── Section 1: Profile Card ───────────────────────────────────────────────
function ProfileCard({ gameName, profile }) {
  const totalGames = profile.wins + profile.losses;
  const wr = totalGames > 0 ? ((profile.wins / totalGames) * 100).toFixed(1) : "—";
  const tierColor = TIER_COLORS[profile.tier] ?? "text-slate-400";
  const rankLabel =
    profile.tier === "UNRANKED"
      ? "Unranked"
      : `${profile.tier} ${profile.division}`;

  return (
    <div className={card("p-6 flex flex-col sm:flex-row items-center sm:items-start gap-5")}>
      {/* Avatar placeholder */}
      <div className="w-16 h-16 rounded-xl bg-[#c89b3c]/10 border border-[#c89b3c]/20 flex items-center justify-center flex-shrink-0">
        <span className="text-2xl font-black text-[#c89b3c]">
          {gameName.charAt(0).toUpperCase()}
        </span>
      </div>

      {/* Info */}
      <div className="flex-1 text-center sm:text-left">
        <h2 className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight leading-none mb-1">
          {gameName}
        </h2>
        <p className="text-xs text-slate-400 dark:text-white/30 mb-3">
          Level {profile.summonerLevel}
        </p>

        <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
          {/* Rank badge */}
          <span className={`text-sm font-bold ${tierColor}`}>
            {rankLabel}
            {profile.tier !== "UNRANKED" && (
              <span className="text-slate-400 dark:text-white/40 font-normal"> • {profile.lp} LP</span>
            )}
          </span>

          {totalGames > 0 && (
            <>
              <span className="text-slate-300 dark:text-white/10">|</span>
              <span className="text-sm text-slate-500 dark:text-white/40">
                <span className="text-emerald-500 font-semibold">{profile.wins}W</span>
                {" "}
                <span className="text-red-400 font-semibold">{profile.losses}L</span>
                <span className="text-slate-400 dark:text-white/30"> • {wr}%</span>
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Section 2: Game Cards ─────────────────────────────────────────────────
function GameCard({ game }) {
  const mins = Math.floor(game.gameDuration / 60);
  const secs = String(game.gameDuration % 60).padStart(2, "0");
  const imgSrc = `https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/${game.championName}.png`;

  return (
    <div className={`${card("p-4 flex flex-col gap-3 min-w-[140px]")} ${
      game.win
        ? "border-emerald-200 dark:border-emerald-500/20"
        : "border-red-200 dark:border-red-500/20"
    }`}>
      {/* Win/loss stripe */}
      <div className={`h-0.5 rounded-full -mt-4 mx-4 mb-1 ${game.win ? "bg-emerald-400" : "bg-red-400"}`} />

      {/* Champion icon */}
      <div className="flex items-center gap-3">
        <img
          src={imgSrc}
          alt={game.championName}
          onError={(e) => { e.target.style.display = "none"; }}
          className="w-10 h-10 rounded-lg object-cover border border-slate-200 dark:border-white/10 flex-shrink-0"
        />
        <div className="min-w-0">
          <p className="font-bold text-slate-900 dark:text-white text-sm truncate leading-tight">
            {game.championName}
          </p>
          <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${
            game.win
              ? "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
              : "bg-red-100 dark:bg-red-500/15 text-red-600 dark:text-red-400"
          }`}>
            {game.win ? "WIN" : "LOSS"}
          </span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
        <Stat label="KDA" value={`${game.kills}/${game.deaths}/${game.assists}`} />
        <Stat label="CS/m" value={game.cspm} />
        <Stat label="Vision" value={game.visionScore} />
        <Stat label="Time" value={`${mins}:${secs}`} />
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <p className="text-slate-400 dark:text-white/30 text-[10px] uppercase tracking-wide leading-none mb-0.5">{label}</p>
      <p className="text-slate-700 dark:text-white/80 font-semibold">{value}</p>
    </div>
  );
}

// ── Section 3a: Stats Table ───────────────────────────────────────────────
const STAT_ROWS = [
  { key: "kda",                        label: "KDA Ratio",     fmt: (v) => v.toFixed(2), invertDelta: false },
  { key: "cspm",                       label: "CS per Minute", fmt: (v) => v.toFixed(2), invertDelta: false },
  { key: "visionScore",                label: "Vision Score",  fmt: (v) => v.toFixed(1), invertDelta: false },
  { key: "totalDamageDealtToChampions",label: "Damage Dealt",  fmt: (v) => Math.round(v).toLocaleString(), invertDelta: false },
  { key: "goldEarned",                 label: "Gold Earned",   fmt: (v) => Math.round(v).toLocaleString(), invertDelta: false },
  { key: "wardsPlaced",                label: "Wards Placed",  fmt: (v) => v.toFixed(1), invertDelta: false },
  { key: "wardsKilled",                label: "Wards Killed",  fmt: (v) => v.toFixed(1), invertDelta: false },
  { key: "deaths",                     label: "Deaths",        fmt: (v) => v.toFixed(1), invertDelta: true  },
];

function StatsTable({ playerAverages, lobbyAverages, deltas }) {
  return (
    <div className={card("overflow-hidden")}>
      <div className="px-5 py-4 border-b border-slate-100 dark:border-white/[0.06]">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-tight">Stats vs Lobby Average</h3>
      </div>
      <div className="divide-y divide-slate-100 dark:divide-white/[0.04]">
        {/* Header */}
        <div className="grid grid-cols-4 px-5 py-2">
          {["Stat", "You", "Lobby", "Delta"].map((h) => (
            <span key={h} className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-white/25">{h}</span>
          ))}
        </div>
        {STAT_ROWS.map(({ key, label, fmt, invertDelta }) => {
          const pVal = playerAverages[key];
          const lVal = lobbyAverages[key];
          const dVal = deltas[key];
          if (pVal == null) return null;

          const isPositive = invertDelta ? dVal < 0 : dVal > 0;
          const deltaColor = Math.abs(dVal) < 0.05
            ? "text-slate-400 dark:text-white/30"
            : isPositive
              ? "text-emerald-500 dark:text-emerald-400"
              : "text-red-500 dark:text-red-400";
          const deltaSign = dVal > 0 ? "+" : "";

          return (
            <div key={key} className="grid grid-cols-4 px-5 py-3 hover:bg-slate-50 dark:hover:bg-white/[0.02] transition-colors">
              <span className="text-xs text-slate-600 dark:text-white/60 font-medium">{label}</span>
              <span className="text-xs font-semibold text-slate-900 dark:text-white">{fmt(pVal)}</span>
              <span className="text-xs text-slate-400 dark:text-white/30">{fmt(lVal)}</span>
              <span className={`text-xs font-semibold ${deltaColor}`}>
                {deltaSign}{typeof dVal === "number" ? dVal.toFixed(2) : "—"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Section 3b: Coaching Panel ────────────────────────────────────────────
function CoachingPanel({ coaching }) {
  const tips = coaching
    .split(/\n+/)
    .map((l) => l.trim())
    .filter((l) => /^\d+[\.\)]/.test(l))
    .map((l) => l.replace(/^\d+[\.\)]\s*/, "").trim());

  const fallback = tips.length === 0;

  return (
    <div className={card("flex flex-col")}>
      <div className="px-5 py-4 border-b border-slate-100 dark:border-white/[0.06] flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-[#c89b3c] animate-pulse" />
        <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-tight">AI Coaching Tips</h3>
      </div>
      <div className="p-5 space-y-3 flex-1">
        {fallback ? (
          <p className="text-sm text-slate-500 dark:text-white/40 leading-relaxed whitespace-pre-wrap">{coaching}</p>
        ) : (
          tips.map((tip, i) => (
            <div key={i} className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[#c89b3c]/10 border border-[#c89b3c]/30 text-[#c89b3c] text-xs font-bold flex items-center justify-center mt-0.5">
                {i + 1}
              </span>
              <p className="text-sm text-slate-700 dark:text-white/70 leading-relaxed">{tip}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────
export default function Dashboard() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const { puuid, gameName } = state ?? {};

  const [profile, setProfile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!puuid) {
      navigate("/");
      return;
    }

    Promise.all([getProfile(puuid), analyzeSummoner(puuid, gameName)])
      .then(([prof, anal]) => {
        setProfile(prof);
        setAnalysis(anal);
      })
      .catch(() => setError("Failed to load data. Check that the backend is running."))
      .finally(() => setLoading(false));
  }, [puuid, gameName, navigate]);

  if (loading) return <LoadingScreen />;
  if (error) return <ErrorScreen message={error} onRetry={() => navigate("/")} />;

  return (
    <div className="min-h-screen pt-20 pb-16 px-4">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* Search Again */}
        <button
          onClick={() => navigate("/")}
          className="text-xs font-semibold text-slate-400 dark:text-white/30 hover:text-[#c89b3c] dark:hover:text-[#c89b3c] transition-colors flex items-center gap-1"
        >
          ← Search Again
        </button>

        {/* Section 1: Profile */}
        <ProfileCard gameName={gameName} profile={profile} />

        {/* Section 2: Recent Games */}
        <div>
          <SectionLabel>Recent Games</SectionLabel>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
            {analysis.games.map((game) => (
              <GameCard key={game.matchId} game={game} />
            ))}
          </div>
        </div>

        {/* Section 3: Coaching */}
        <div>
          <SectionLabel>Analysis</SectionLabel>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <StatsTable
              playerAverages={analysis.playerAverages}
              lobbyAverages={analysis.lobbyAverages}
              deltas={analysis.deltas}
            />
            <CoachingPanel coaching={analysis.coaching} />
          </div>
        </div>

      </div>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <h2 className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25 mb-3">
      {children}
    </h2>
  );
}
