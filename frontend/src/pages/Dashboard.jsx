import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { getProfile, analyzeSummoner, getScoreboard } from "../api/riot";

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

function computePerformanceScore(player, allPlayers) {
  const avg = (fn) => allPlayers.reduce((s, p) => s + fn(p), 0) / allPlayers.length;
  const avgKDA = avg((p) => (p.kills + p.assists) / Math.max(p.deaths, 1));
  const avgDmg = avg((p) => p.totalDamageDealtToChampions);
  const avgGold = avg((p) => p.goldEarned);
  const avgCS = avg((p) => p.totalMinionsKilled);
  const pKDA = (player.kills + player.assists) / Math.max(player.deaths, 1);
  const raw =
    (pKDA / Math.max(avgKDA, 0.1)) * 30 +
    (player.totalDamageDealtToChampions / Math.max(avgDmg, 1)) * 30 +
    (player.goldEarned / Math.max(avgGold, 1)) * 20 +
    (player.totalMinionsKilled / Math.max(avgCS, 1)) * 20;
  return Math.min(10, Math.max(0, raw / 10)).toFixed(1);
}

// ── Loading ────────────────────────────────────────────────────────────────
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

// ── LP Trend Graph ─────────────────────────────────────────────────────────
function LPGraph({ games }) {
  const ordered = [...games].reverse();
  const trend = [0];
  ordered.forEach((g) => {
    trend.push(trend[trend.length - 1] + (g.win ? 20 : -17));
  });

  const min = Math.min(...trend);
  const max = Math.max(...trend);
  const range = Math.max(max - min, 30);
  const W = 260, H = 52;
  const padX = 8, padY = 8;
  const innerW = W - 2 * padX;
  const innerH = H - 2 * padY;
  const toX = (i) => padX + (i / (trend.length - 1)) * innerW;
  const toY = (v) => padY + innerH - ((v - min) / range) * innerH;
  const pathD = trend.map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(v).toFixed(1)}`).join(" ");
  const areaD = `${pathD} L ${toX(trend.length - 1).toFixed(1)} ${(padY + innerH).toFixed(1)} L ${toX(0).toFixed(1)} ${(padY + innerH).toFixed(1)} Z`;
  const lastDelta = trend[trend.length - 1];
  const lineColor = lastDelta >= 0 ? "#10b981" : "#ef4444";

  return (
    <div className="mt-4 pt-4 border-t border-slate-100 dark:border-white/[0.06]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-white/25">
          LP Trend · Last 5
        </span>
        <span className={`text-xs font-bold ${lastDelta >= 0 ? "text-emerald-500" : "text-red-400"}`}>
          {lastDelta >= 0 ? "+" : ""}{lastDelta} LP est.
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 52 }}>
        <defs>
          <linearGradient id="lpGradFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.18" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#lpGradFill)" />
        <path d={pathD} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        {trend.map((v, i) => (
          <circle
            key={i}
            cx={toX(i).toFixed(1)}
            cy={toY(v).toFixed(1)}
            r="2.8"
            fill={i === 0 ? "#475569" : ordered[i - 1]?.win ? "#10b981" : "#ef4444"}
          />
        ))}
      </svg>
      <div className="flex justify-between text-[10px] text-slate-400 dark:text-white/20 mt-0.5">
        <span>5 games ago</span>
        <span>Now</span>
      </div>
    </div>
  );
}

// ── Profile Card ───────────────────────────────────────────────────────────
function ProfileCard({ gameName, profile, games }) {
  const totalGames = profile.wins + profile.losses;
  const wr = totalGames > 0 ? ((profile.wins / totalGames) * 100).toFixed(1) : "—";
  const tierColor = TIER_COLORS[profile.tier] ?? "text-slate-400";
  const rankLabel =
    profile.tier === "UNRANKED" ? "Unranked" : `${profile.tier} ${profile.division}`;

  return (
    <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl shadow-sm dark:shadow-black/40 p-5">
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-xl bg-[#c89b3c]/10 border border-[#c89b3c]/20 flex items-center justify-center flex-shrink-0">
          <span className="text-2xl font-black text-[#c89b3c]">{gameName.charAt(0).toUpperCase()}</span>
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-extrabold text-slate-900 dark:text-white tracking-tight leading-none mb-0.5 truncate">
            {gameName}
          </h2>
          <p className="text-xs text-slate-400 dark:text-white/30 mb-2">Level {profile.summonerLevel}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className={`text-sm font-bold ${tierColor}`}>
              {rankLabel}
              {profile.tier !== "UNRANKED" && (
                <span className="text-slate-400 dark:text-white/40 font-normal"> · {profile.lp} LP</span>
              )}
            </span>
            {totalGames > 0 && (
              <span className="text-sm text-slate-500 dark:text-white/40">
                <span className="text-emerald-500 font-semibold">{profile.wins}W</span>{" "}
                <span className="text-red-400 font-semibold">{profile.losses}L</span>
                <span className="text-slate-400 dark:text-white/30"> · {wr}%</span>
              </span>
            )}
          </div>
        </div>
      </div>
      {games && <LPGraph games={games} />}
    </div>
  );
}

// ── Expanded Scoreboard ────────────────────────────────────────────────────
function TeamScoreRows({ players, isWin, teamLabel, gameName }) {
  return (
    <>
      <tr>
        <td colSpan={8} className={`px-4 py-1.5 ${
          isWin
            ? "bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400"
            : "bg-red-50 dark:bg-red-950/50 text-red-500 dark:text-red-400"
        }`}>
          <span className="text-[10px] font-bold uppercase tracking-widest">
            {teamLabel} — {isWin ? "Victory" : "Defeat"}
          </span>
        </td>
      </tr>
      {players.map((p, idx) => {
        const isMe = p.riotIdGameName === gameName;
        const scoreNum = parseFloat(p.score);
        const scoreColor =
          scoreNum >= 7
            ? "text-emerald-500 dark:text-emerald-400"
            : scoreNum >= 4.5
            ? "text-[#c89b3c]"
            : "text-slate-400 dark:text-white/40";
        return (
          <tr
            key={p.riotIdGameName + p.championName}
            className={`border-b border-black/[0.04] dark:border-white/[0.03] last:border-0 transition-colors ${
              isMe
                ? "bg-[#c89b3c]/10 dark:bg-[#c89b3c]/[0.12]"
                : "hover:bg-black/[0.02] dark:hover:bg-white/[0.02]"
            }`}
          >
            <td className="px-4 py-2.5 text-slate-400 dark:text-white/25 text-[10px] w-7">{idx + 1}</td>
            <td className="px-3 py-2.5">
              <div className="flex items-center gap-2">
                <img
                  src={`https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/${p.championName}.png`}
                  alt={p.championName}
                  onError={(e) => { e.target.style.display = "none"; }}
                  className="w-6 h-6 rounded object-cover border border-slate-200 dark:border-white/10 flex-shrink-0"
                />
                <span className={`font-semibold truncate max-w-[110px] text-xs ${
                  isMe ? "text-[#c89b3c]" : "text-slate-700 dark:text-white/70"
                }`}>
                  {isMe && "★ "}{p.riotIdGameName || "Unknown"}
                </span>
              </div>
            </td>
            <td className="px-3 py-2.5 text-center text-slate-700 dark:text-white/70 font-medium whitespace-nowrap text-xs">
              {p.kills}/{p.deaths}/{p.assists}
            </td>
            <td className="px-3 py-2.5 text-center text-slate-500 dark:text-white/40 text-xs">{p.totalMinionsKilled}</td>
            <td className="px-3 py-2.5 text-center text-slate-500 dark:text-white/40 text-xs">{p.visionScore}</td>
            <td className="px-3 py-2.5 text-center text-slate-500 dark:text-white/40 text-xs">
              {(p.totalDamageDealtToChampions / 1000).toFixed(1)}k
            </td>
            <td className="px-3 py-2.5 text-center text-slate-500 dark:text-white/40 text-xs">
              {(p.goldEarned / 1000).toFixed(1)}k
            </td>
            <td className="px-3 py-2.5 text-center">
              <span className={`font-bold text-sm ${scoreColor}`}>{p.score}</span>
            </td>
          </tr>
        );
      })}
    </>
  );
}

function ExpandedScoreboard({ scoreboard, loading, gameName }) {
  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center gap-3">
        <div className="w-4 h-4 rounded-full border-2 border-t-[#c89b3c] border-[#c89b3c]/20 animate-spin" />
        <span className="text-sm text-slate-400 dark:text-white/30">Loading scoreboard...</span>
      </div>
    );
  }
  if (!scoreboard) return null;

  const withScores = scoreboard.map((p) => ({
    ...p,
    score: computePerformanceScore(p, scoreboard),
  }));
  const team100Won = scoreboard.find((p) => p.teamId === 100)?.win ?? true;

  return (
    <div className="overflow-x-auto animate-slideDown">
      <table className="w-full min-w-[540px]">
        <thead>
          <tr className="border-b border-black/[0.07] dark:border-white/[0.07]">
            <th className="px-4 py-2 w-7" />
            <th className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">Player</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">KDA</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">CS</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">Vis</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">Dmg</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">Gold</th>
            <th className="px-3 py-2 text-center text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">Score</th>
          </tr>
        </thead>
        <tbody>
          <TeamScoreRows
            players={withScores.filter((p) => p.teamId === 100)}
            isWin={team100Won}
            teamLabel="Blue Team"
            gameName={gameName}
          />
          <tr>
            <td colSpan={8} className="p-0">
              <div className="h-px bg-black/10 dark:bg-white/[0.08]" />
            </td>
          </tr>
          <TeamScoreRows
            players={withScores.filter((p) => p.teamId === 200)}
            isWin={!team100Won}
            teamLabel="Red Team"
            gameName={gameName}
          />
        </tbody>
      </table>
    </div>
  );
}

// ── Horizontal Game Row ────────────────────────────────────────────────────
function GameRow({ game, isExpanded, onToggle, scoreboard, scoreboardLoading, gameName }) {
  const mins = Math.floor(game.gameDuration / 60);
  const secs = String(game.gameDuration % 60).padStart(2, "0");
  const imgSrc = `https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/${game.championName}.png`;
  const kda = ((game.kills + game.assists) / Math.max(game.deaths, 1)).toFixed(2);

  return (
    <div
      className={`rounded-xl overflow-hidden border transition-all duration-300
        ${game.win
          ? "border-emerald-200 dark:border-emerald-500/25"
          : "border-red-200 dark:border-red-500/25"
        }
        ${isExpanded ? "ring-1 ring-[#c89b3c]/40 shadow-lg shadow-[#c89b3c]/5" : ""}`}
    >
      {/* Clickable header */}
      <div
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer select-none transition-colors duration-200
          ${game.win
            ? "bg-emerald-50/70 dark:bg-emerald-950/25 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
            : "bg-red-50/70 dark:bg-red-950/25 hover:bg-red-50 dark:hover:bg-red-950/40"
          }`}
        onClick={onToggle}
      >
        {/* Left accent bar */}
        <div className={`w-1 h-12 rounded-full flex-shrink-0 ${game.win ? "bg-emerald-400" : "bg-red-400"}`} />

        {/* Champion icon */}
        <img
          src={imgSrc}
          alt={game.championName}
          onError={(e) => { e.target.style.display = "none"; }}
          className="w-12 h-12 rounded-lg object-cover border border-slate-200 dark:border-white/10 flex-shrink-0"
        />

        {/* Champion + result */}
        <div className="w-36 flex-shrink-0 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-slate-900 dark:text-white text-sm truncate">{game.championName}</span>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${
              game.win
                ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                : "bg-red-100 dark:bg-red-500/20 text-red-500 dark:text-red-400"
            }`}>
              {game.win ? "W" : "L"}
            </span>
          </div>
          <div className="text-[11px] text-slate-400 dark:text-white/30 mt-0.5">
            {game.teamPosition || "—"} · {mins}:{secs}
          </div>
        </div>

        {/* Stats */}
        <div className="flex-1 flex items-center gap-5 min-w-0">
          <div>
            <div className="text-sm font-bold text-slate-900 dark:text-white whitespace-nowrap">
              {game.kills}{" "}
              <span className="text-slate-400 dark:text-white/30">/</span>{" "}
              <span className={game.deaths >= 7 ? "text-red-400" : ""}>{game.deaths}</span>{" "}
              <span className="text-slate-400 dark:text-white/30">/</span>{" "}
              {game.assists}
            </div>
            <div className="text-[10px] text-slate-400 dark:text-white/25 uppercase tracking-wide">{kda} KDA</div>
          </div>

          <div className="hidden sm:block">
            <div className="text-sm font-semibold text-slate-700 dark:text-white/60">{game.cspm}</div>
            <div className="text-[10px] text-slate-400 dark:text-white/25 uppercase tracking-wide">CS/m</div>
          </div>

          <div className="hidden md:block">
            <div className="text-sm font-semibold text-slate-700 dark:text-white/60">{game.visionScore}</div>
            <div className="text-[10px] text-slate-400 dark:text-white/25 uppercase tracking-wide">Vision</div>
          </div>
        </div>

        {/* Expand toggle */}
        <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center transition-all duration-200 ${
          isExpanded ? "bg-[#c89b3c]/20 text-[#c89b3c] rotate-0" : "text-slate-400 dark:text-white/20"
        }`}>
          <span className="text-[10px] font-bold">{isExpanded ? "▲" : "▼"}</span>
        </div>
      </div>

      {/* Expanded scoreboard */}
      {isExpanded && (
        <div className={`border-t ${
          game.win
            ? "border-emerald-200 dark:border-emerald-500/20 bg-emerald-50/20 dark:bg-emerald-950/10"
            : "border-red-200 dark:border-red-500/20 bg-red-50/20 dark:bg-red-950/10"
        }`}>
          <ExpandedScoreboard scoreboard={scoreboard} loading={scoreboardLoading} gameName={gameName} />
        </div>
      )}
    </div>
  );
}

// ── Stats Table ────────────────────────────────────────────────────────────
const STAT_ROWS = [
  { key: "kda",                         label: "KDA Ratio",     fmt: (v) => v.toFixed(2),                 invertDelta: false },
  { key: "cspm",                        label: "CS per Minute", fmt: (v) => v.toFixed(2),                 invertDelta: false },
  { key: "visionScore",                 label: "Vision Score",  fmt: (v) => v.toFixed(1),                 invertDelta: false },
  { key: "totalDamageDealtToChampions", label: "Damage Dealt",  fmt: (v) => (v / 1000).toFixed(1) + "k", invertDelta: false },
  { key: "goldEarned",                  label: "Gold Earned",   fmt: (v) => (v / 1000).toFixed(1) + "k", invertDelta: false },
  { key: "wardsPlaced",                 label: "Wards Placed",  fmt: (v) => v.toFixed(1),                 invertDelta: false },
  { key: "wardsKilled",                 label: "Wards Killed",  fmt: (v) => v.toFixed(1),                 invertDelta: false },
  { key: "deaths",                      label: "Deaths",        fmt: (v) => v.toFixed(1),                 invertDelta: true  },
];

function StatsContent({ playerAverages, lobbyAverages, deltas }) {
  return (
    <div className="divide-y divide-slate-100 dark:divide-white/[0.04]">
      <div className="grid grid-cols-4 px-5 py-2">
        {["Stat", "You", "Lobby", "Δ"].map((h) => (
          <span key={h} className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-white/25">{h}</span>
        ))}
      </div>
      {STAT_ROWS.map(({ key, label, fmt, invertDelta }) => {
        const pVal = playerAverages[key];
        const lVal = lobbyAverages[key];
        const dVal = deltas[key];
        if (pVal == null) return null;
        const isPositive = invertDelta ? dVal < 0 : dVal > 0;
        const deltaColor =
          Math.abs(dVal) < 0.05
            ? "text-slate-400 dark:text-white/30"
            : isPositive
            ? "text-emerald-500 dark:text-emerald-400"
            : "text-red-500 dark:text-red-400";
        return (
          <div key={key} className="grid grid-cols-4 px-5 py-2.5 hover:bg-slate-50 dark:hover:bg-white/[0.02] transition-colors">
            <span className="text-xs text-slate-600 dark:text-white/60 font-medium">{label}</span>
            <span className="text-xs font-semibold text-slate-900 dark:text-white">{fmt(pVal)}</span>
            <span className="text-xs text-slate-400 dark:text-white/30">{fmt(lVal)}</span>
            <span className={`text-xs font-semibold ${deltaColor}`}>
              {dVal > 0 ? "+" : ""}{typeof dVal === "number" ? dVal.toFixed(2) : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Right Panel (tabbed: Coaching | Stats) ─────────────────────────────────
function RightPanel({ coaching, playerAverages, lobbyAverages, deltas }) {
  const [tab, setTab] = useState("coaching");

  const tips = coaching
    .split(/\n+/)
    .map((l) => l.trim())
    .filter((l) => /^\d+[\.\)]/.test(l))
    .map((l) => l.replace(/^\d+[\.\)]\s*/, "").trim());

  const fallback = tips.length === 0;

  return (
    <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl shadow-sm dark:shadow-black/40 flex flex-col">
      {/* Tab bar */}
      <div className="flex border-b border-slate-100 dark:border-white/[0.06]">
        {[
          { id: "coaching", label: "AI Coaching", dot: true },
          { id: "stats",    label: "Stats",        dot: false },
        ].map(({ id, label, dot }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-4 py-3.5 text-xs font-semibold tracking-wide transition-colors duration-150
              ${tab === id
                ? "text-slate-900 dark:text-white border-b-2 border-[#c89b3c] -mb-px"
                : "text-slate-400 dark:text-white/30 hover:text-slate-600 dark:hover:text-white/50"
              }`}
          >
            {dot && tab === id && <span className="w-1.5 h-1.5 rounded-full bg-[#c89b3c] animate-pulse" />}
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 animate-fadeIn" key={tab}>
        {tab === "coaching" ? (
          <div className="p-5 space-y-4">
            {fallback ? (
              <div className="text-sm text-slate-600 dark:text-white/60 leading-relaxed
                [&_strong]:font-bold [&_strong]:text-slate-900 [&_strong]:dark:text-white
                [&_em]:italic [&_p]:mb-2 [&_p:last-child]:mb-0">
                <ReactMarkdown>{coaching}</ReactMarkdown>
              </div>
            ) : (
              tips.map((tip, i) => (
                <div key={i} className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[#c89b3c]/10 border border-[#c89b3c]/30 text-[#c89b3c] text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </span>
                  <div className="text-sm text-slate-700 dark:text-white/70 leading-relaxed
                    [&_strong]:font-bold [&_strong]:text-slate-900 [&_strong]:dark:text-white [&_em]:italic">
                    <ReactMarkdown>{tip}</ReactMarkdown>
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <StatsContent
            playerAverages={playerAverages}
            lobbyAverages={lobbyAverages}
            deltas={deltas}
          />
        )}
      </div>
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────
export default function Dashboard() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const { puuid, gameName } = state ?? {};

  const [profile, setProfile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [expandedMatchId, setExpandedMatchId] = useState(null);
  const [scoreboard, setScoreboard] = useState(null);
  const [scoreboardLoading, setScoreboardLoading] = useState(false);

  useEffect(() => {
    if (!puuid) { navigate("/"); return; }
    Promise.all([getProfile(puuid), analyzeSummoner(puuid, gameName)])
      .then(([prof, anal]) => { setProfile(prof); setAnalysis(anal); })
      .catch(() => setError("Failed to load data. Check that the backend is running."))
      .finally(() => setLoading(false));
  }, [puuid, gameName, navigate]);

  const handleToggleGame = async (matchId) => {
    if (expandedMatchId === matchId) {
      setExpandedMatchId(null);
      setScoreboard(null);
      return;
    }
    setExpandedMatchId(matchId);
    setScoreboard(null);
    setScoreboardLoading(true);
    try {
      const data = await getScoreboard(matchId);
      setScoreboard(data);
    } catch {
      setScoreboard(null);
    } finally {
      setScoreboardLoading(false);
    }
  };

  if (loading) return <LoadingScreen />;
  if (error) return <ErrorScreen message={error} onRetry={() => navigate("/")} />;

  return (
    <div className="min-h-screen pt-20 pb-16 px-4 animate-fadeIn">
      <div className="max-w-6xl mx-auto">

        <button
          onClick={() => navigate("/")}
          className="text-xs font-semibold text-slate-400 dark:text-white/30 hover:text-[#c89b3c] dark:hover:text-[#c89b3c] transition-colors flex items-center gap-1 mb-4"
        >
          ← Search Again
        </button>

        <div className="flex flex-col lg:flex-row gap-5 items-start">

          {/* Left — profile + match history */}
          <div className="flex-1 min-w-0 space-y-4">

            <ProfileCard gameName={gameName} profile={profile} games={analysis.games} />

            <div>
              <SectionLabel>Match History</SectionLabel>
              <div className="space-y-2">
                {analysis.games.map((game) => (
                  <GameRow
                    key={game.matchId}
                    game={game}
                    isExpanded={expandedMatchId === game.matchId}
                    onToggle={() => handleToggleGame(game.matchId)}
                    scoreboard={expandedMatchId === game.matchId ? scoreboard : null}
                    scoreboardLoading={expandedMatchId === game.matchId && scoreboardLoading}
                    gameName={gameName}
                  />
                ))}
              </div>
            </div>

          </div>

          {/* Right — sticky tabbed panel */}
          <div className="w-full lg:w-80 xl:w-96 flex-shrink-0 lg:sticky lg:top-20">
            <RightPanel
              coaching={analysis.coaching}
              playerAverages={analysis.playerAverages}
              lobbyAverages={analysis.lobbyAverages}
              deltas={analysis.deltas}
            />
          </div>

        </div>
      </div>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <h2 className="text-[11px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25 mb-2">
      {children}
    </h2>
  );
}
