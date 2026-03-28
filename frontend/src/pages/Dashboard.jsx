import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { getProfile, analyzeSummoner, getScoreboard, getHistory, getSummoner, askCoach } from "../api/riot";
import { readSaved, writeSaved } from "../components/Navbar";

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
  const avgVis = avg((p) => p.visionScore);

  const raw = (p) => {
    const kda = (p.kills + p.assists) / Math.max(p.deaths, 1);
    return (kda / Math.max(avgKDA, 0.1)) * 25 +
           (p.totalDamageDealtToChampions / Math.max(avgDmg, 1)) * 25 +
           (p.goldEarned / Math.max(avgGold, 1)) * 20 +
           (p.totalMinionsKilled / Math.max(avgCS, 1)) * 15 +
           (p.visionScore / Math.max(avgVis, 1)) * 15;
  };

  const myRaw = raw(player);
  // rank = number of players with a higher raw score (0 = best in lobby)
  const rank = allPlayers.filter((p) => raw(p) > myRaw).length;
  const scoreTable = [100, 93, 83, 75, 72, 64, 61, 58, 49, 25];
  return scoreTable[Math.min(rank, 9)];
}

// ── Skeleton loading ────────────────────────────────────────────────────────
function Sk({ className = "" }) {
  return <div className={`skeleton ${className}`} />;
}

function SkeletonDashboard() {
  return (
    <div className="min-h-screen pt-20 pb-16 px-4 animate-fadeIn">
      <div className="max-w-6xl mx-auto">
        <Sk className="h-3.5 w-20 mb-5" />

        <div className="flex flex-col lg:flex-row gap-5 items-start">
          {/* Left column */}
          <div className="flex-1 min-w-0 space-y-4">

            {/* Profile card */}
            <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl p-5">
              <div className="flex items-center gap-4">
                <Sk className="w-14 h-14 rounded-xl flex-shrink-0" />
                <div className="flex-1 space-y-2.5">
                  <Sk className="h-5 w-36" />
                  <Sk className="h-3 w-14" />
                  <Sk className="h-4 w-52" />
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-100 dark:border-white/[0.06]">
                <div className="flex justify-between mb-2">
                  <Sk className="h-2.5 w-20" />
                  <Sk className="h-2.5 w-14" />
                </div>
                <Sk className="h-[52px] w-full" />
                <div className="flex justify-between mt-1.5">
                  <Sk className="h-2 w-16" />
                  <Sk className="h-2 w-6" />
                </div>
              </div>
            </div>

            {/* Match rows */}
            <div>
              <Sk className="h-2.5 w-24 mb-2" />
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="rounded-xl overflow-hidden border border-slate-200 dark:border-white/[0.07]">
                    <div className="flex items-center gap-3 px-4 py-3 bg-slate-50/50 dark:bg-white/[0.01]">
                      <Sk className="w-1 h-12 rounded-full flex-shrink-0" />
                      <Sk className="w-12 h-12 rounded-lg flex-shrink-0" />
                      <div className="w-36 flex-shrink-0 space-y-1.5">
                        <Sk className="h-4 w-28" />
                        <Sk className="h-3 w-20" />
                      </div>
                      <div className="flex-1 flex items-center gap-5">
                        <div className="space-y-1.5">
                          <Sk className="h-4 w-16" />
                          <Sk className="h-2.5 w-12" />
                        </div>
                        <div className="hidden sm:block space-y-1.5">
                          <Sk className="h-4 w-10" />
                          <Sk className="h-2.5 w-8" />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right panel */}
          <div className="w-full lg:w-80 xl:w-96 flex-shrink-0">
            <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl overflow-hidden">
              <div className="flex border-b border-slate-100 dark:border-white/[0.06]">
                <div className="flex-1 py-3.5 px-4 flex items-center justify-center">
                  <Sk className="h-3.5 w-20" />
                </div>
                <div className="w-px bg-slate-100 dark:bg-white/[0.06]" />
                <div className="flex-1 py-3.5 px-4 flex items-center justify-center">
                  <Sk className="h-3.5 w-12" />
                </div>
              </div>
              <div className="p-5 space-y-5">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="flex gap-3">
                    <Sk className="w-6 h-6 rounded-full flex-shrink-0" />
                    <div className="flex-1 space-y-2">
                      <Sk className="h-3.5 w-full" />
                      <Sk className={`h-3.5 ${i % 2 === 0 ? "w-4/5" : "w-3/5"}`} />
                      <Sk className={`h-3.5 ${i % 3 === 0 ? "w-3/5" : "w-2/3"}`} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
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
          LP Trend · Last {games.length}
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
        <span>{games.length} games ago</span>
        <span>Now</span>
      </div>
    </div>
  );
}

// ── Star / save button ─────────────────────────────────────────────────────
function StarButton({ gameName, tagLine, puuid }) {
  const [saved, setSaved] = useState(() =>
    readSaved().some((p) => p.puuid === puuid)
  );

  // nothing to save if we don't have a tagLine (shouldn't happen, but safe)
  if (!tagLine || !puuid) return null;

  const toggle = () => {
    const current = readSaved();
    if (saved) {
      writeSaved(current.filter((p) => p.puuid !== puuid));
      setSaved(false);
    } else {
      if (current.length >= 10) return;
      writeSaved([...current, { gameName, tagLine, puuid }]);
      setSaved(true);
    }
  };

  return (
    <button
      onClick={toggle}
      title={saved ? "Remove from saved" : "Save profile"}
      className={`ml-1 flex-shrink-0 text-lg leading-none transition-colors duration-150
        ${saved ? "text-[#c89b3c]" : "text-slate-300 dark:text-white/20 hover:text-[#c89b3c]"}`}
    >
      {saved ? "★" : "☆"}
    </button>
  );
}

const LANE_META = {
  TOP:     { abbr: "TOP", color: "text-blue-400",   bg: "bg-blue-400/10",   border: "border-blue-400/25"   },
  JUNGLE:  { abbr: "JGL", color: "text-green-400",  bg: "bg-green-400/10",  border: "border-green-400/25"  },
  MIDDLE:  { abbr: "MID", color: "text-purple-400", bg: "bg-purple-400/10", border: "border-purple-400/25" },
  BOTTOM:  { abbr: "BOT", color: "text-orange-400", bg: "bg-orange-400/10", border: "border-orange-400/25" },
  UTILITY: { abbr: "SUP", color: "text-yellow-400", bg: "bg-yellow-400/10", border: "border-yellow-400/25" },
};

function LaneIcon({ lane }) {
  const m = LANE_META[lane] ?? { abbr: lane ?? "?", color: "text-slate-400", bg: "bg-slate-400/10", border: "border-slate-400/25" };
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wide flex-shrink-0 ${m.color} ${m.bg} ${m.border}`}>
      {m.abbr}
    </span>
  );
}

const TIER_EMBLEM = {
  IRON: "Iron", BRONZE: "Bronze", SILVER: "Silver", GOLD: "Gold",
  PLATINUM: "Platinum", EMERALD: "Emerald", DIAMOND: "Diamond",
  MASTER: "Master", GRANDMASTER: "Grandmaster", CHALLENGER: "Challenger",
};

// ── Profile Card ───────────────────────────────────────────────────────────
function ProfileCard({ gameName, tagLine, puuid, profile, games, ddVersion }) {
  const totalGames = profile.wins + profile.losses;
  const wr = totalGames > 0 ? ((profile.wins / totalGames) * 100).toFixed(1) : "-";
  const tierColor = TIER_COLORS[profile.tier] ?? "text-slate-400";
  const rankLabel =
    profile.tier === "UNRANKED" ? "Unranked" : `${profile.tier} ${profile.division}`;
  const emblemName = TIER_EMBLEM[profile.tier];
  const emblemUrl = emblemName
    ? `https://ddragon.leagueoflegends.com/cdn/img/ranked-emblems/Emblem_${emblemName}.png`
    : null;
  const iconUrl = profile.profileIconId != null
    ? `https://ddragon.leagueoflegends.com/cdn/${ddVersion}/img/profileicon/${profile.profileIconId}.png`
    : null;

  const [iconFailed, setIconFailed] = useState(false);

  return (
    <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl shadow-sm dark:shadow-black/40 p-5">
      <div className="flex items-center gap-4">
        {/* Profile icon with rank emblem badge */}
        <div className="relative flex-shrink-0">
          <div className="w-14 h-14 rounded-xl bg-[#c89b3c]/10 border border-[#c89b3c]/20 flex items-center justify-center overflow-hidden">
            {iconUrl && !iconFailed ? (
              <img
                src={iconUrl}
                alt="profile icon"
                className="w-full h-full object-cover"
                onError={() => setIconFailed(true)}
              />
            ) : (
              <span className="text-2xl font-black text-[#c89b3c]">
                {gameName.charAt(0).toUpperCase()}
              </span>
            )}
          </div>
          {emblemUrl && (
            <img
              src={emblemUrl}
              alt={profile.tier}
              className="absolute -bottom-1.5 -right-1.5 w-7 h-7 object-contain drop-shadow-sm"
              onError={(e) => { e.target.style.display = "none"; }}
            />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-0.5 mb-0.5">
            <h2 className="text-lg font-extrabold text-slate-900 dark:text-white tracking-tight leading-none truncate">
              {gameName}
            </h2>
            <span className="text-xs text-slate-400 dark:text-white/25 font-normal ml-1 flex-shrink-0">
              #{tagLine}
            </span>
            <StarButton gameName={gameName} tagLine={tagLine} puuid={puuid} />
          </div>
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
            {teamLabel}: {isWin ? "Victory" : "Defeat"}
          </span>
        </td>
      </tr>
      {players.map((p, idx) => {
        const isMe = p.riotIdGameName === gameName;
        const scoreNum = parseFloat(p.score);
        const scoreColor =
          scoreNum >= 79
            ? "text-emerald-500 dark:text-emerald-400"
            : scoreNum >= 50
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
  const scoreColor = game.score >= 79
    ? "text-emerald-500 dark:text-emerald-400"
    : game.score >= 50
    ? "text-[#c89b3c]"
    : "text-slate-400 dark:text-white/40";

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
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[11px] text-slate-400 dark:text-white/30">
              {game.teamPosition || "-"} · {mins}:{secs}
            </span>
            {game.diffedLane && (
              <span className="flex items-center gap-0.5 flex-shrink-0">
                <LaneIcon lane={game.diffedLane} />
                <span className="text-[10px] text-slate-400 dark:text-white/30 truncate">Diff</span>
              </span>
            )}
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

        {/* Score */}
        {game.score != null && (
          <div className="flex flex-col items-center flex-shrink-0">
            <span className={`text-sm font-black tabular-nums ${scoreColor}`}>{game.score}</span>
            <span className="text-[10px] text-slate-400 dark:text-white/25 uppercase tracking-wide">Score</span>
          </div>
        )}

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
              {dVal > 0 ? "+" : ""}{typeof dVal === "number" ? dVal.toFixed(2) : "-"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Summary Strip ───────────────────────────────────────────────────────────
function SummaryStrip({ analysis }) {
  const wins  = analysis.games.filter((g) => g.win).length;
  const losses = analysis.games.length - wins;
  const items = [
    {
      label: "Win Rate",
      value: `${analysis.winRate}%`,
      sub: `${wins}W · ${losses}L`,
      positive: analysis.winRate >= 50,
    },
    {
      label: "Avg KDA",
      value: analysis.playerAverages.kda.toFixed(2),
      sub: `Lobby ${analysis.lobbyAverages.kda.toFixed(2)}`,
      positive: analysis.deltas.kda >= 0,
    },
    {
      label: "CS / min",
      value: analysis.playerAverages.cspm.toFixed(2),
      sub: `Lobby ${analysis.lobbyAverages.cspm.toFixed(2)}`,
      positive: analysis.deltas.cspm >= 0,
    },
    {
      label: "Vision",
      value: analysis.playerAverages.visionScore.toFixed(1),
      sub: `Lobby ${analysis.lobbyAverages.visionScore.toFixed(1)}`,
      positive: analysis.deltas.visionScore >= 0,
    },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {items.map(({ label, value, sub, positive }) => (
        <div
          key={label}
          className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-xl p-3 text-center"
        >
          <div className={`text-xl font-black tabular-nums ${positive ? "text-emerald-500" : "text-red-400"}`}>
            {value}
          </div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25 mt-0.5">
            {label}
          </div>
          <div className="text-[10px] text-slate-400 dark:text-white/20 mt-0.5">{sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Right Panel (tabbed: Coaching | Stats) ─────────────────────────────────
function RightPanel({ coaching, playerAverages, lobbyAverages, deltas, playerContext }) {
  const [tab, setTab] = useState("coaching");
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  const tips = coaching
    .split(/\n(?=\d+[\.\)])/g)
    .map((s) => s.trim())
    .filter((s) => /^\d+[\.\)]/.test(s))
    .map((s) => s.replace(/^\d+[\.\)]\s*/, "").trim());

  const fallback = tips.length === 0;

  const handleAsk = async (e) => {
    e.preventDefault();
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    const userMsg = { role: "user", content: q };
    const next = [...chatHistory, userMsg];
    setChatHistory(next);
    setChatInput("");
    setChatLoading(true);
    try {
      const { answer } = await askCoach(q, playerContext, chatHistory);
      setChatHistory([...next, { role: "assistant", content: answer }]);
    } catch {
      setChatHistory([...next, { role: "assistant", content: "Sorry, something went wrong. Try again." }]);
    } finally {
      setChatLoading(false);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, chatLoading]);

  return (
    <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl shadow-sm dark:shadow-black/40 flex flex-col lg:max-h-[calc(100vh-5.5rem)] lg:overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-slate-100 dark:border-white/[0.06] flex-shrink-0">
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
      <div className="lg:flex-1 lg:min-h-0 lg:flex lg:flex-col animate-fadeIn" key={tab}>
        {tab === "coaching" ? (
          <div className="flex flex-col lg:flex-1 lg:min-h-0 lg:overflow-hidden">
            {/* Tips */}
            <div className="p-5 space-y-4 lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
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

            {/* Chat */}
            <div className="border-t border-slate-100 dark:border-white/[0.06] flex-shrink-0">
              {chatHistory.length > 0 && (
                <div className="px-4 pt-4 pb-2 space-y-3 max-h-72 overflow-y-auto">
                  {chatHistory.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                      {msg.role === "assistant" && (
                        <span className="w-5 h-5 rounded-full bg-[#c89b3c]/15 border border-[#c89b3c]/30 text-[#c89b3c] text-[9px] font-black flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
                          AI
                        </span>
                      )}
                      <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed
                        ${msg.role === "user"
                          ? "bg-[#c89b3c]/10 dark:bg-[#c89b3c]/15 text-slate-800 dark:text-white/80 rounded-tr-sm"
                          : "bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-white/70 rounded-tl-sm"
                        }`}>
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="flex justify-start">
                      <span className="w-5 h-5 rounded-full bg-[#c89b3c]/15 border border-[#c89b3c]/30 text-[#c89b3c] text-[9px] font-black flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
                        AI
                      </span>
                      <div className="bg-slate-100 dark:bg-white/[0.06] rounded-xl rounded-tl-sm px-3 py-2.5 flex items-center gap-1">
                        {[0, 1, 2].map((d) => (
                          <span key={d} className="w-1.5 h-1.5 rounded-full bg-slate-400 dark:bg-white/30 animate-pulse" style={{ animationDelay: `${d * 150}ms` }} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              <div ref={chatEndRef} />

              {/* Input */}
              <form onSubmit={handleAsk} className="p-3">
                <div className="flex items-center gap-2 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.03] px-3 py-2 focus-within:border-[#c89b3c]/50 transition-colors">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask about your gameplay..."
                    className="flex-1 text-xs bg-transparent text-slate-800 dark:text-white placeholder-slate-400 dark:placeholder-white/20 focus:outline-none"
                  />
                  <button
                    type="submit"
                    disabled={!chatInput.trim() || chatLoading}
                    className="flex-shrink-0 w-6 h-6 rounded-lg bg-[#c89b3c] disabled:opacity-30 flex items-center justify-center transition-opacity"
                  >
                    <svg className="w-3 h-3 text-[#1a1000]" viewBox="0 0 12 12" fill="none">
                      <path d="M1 6h10M6 1l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                </div>
              </form>
            </div>
          </div>
        ) : (
          <div className="lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
            <StatsContent
              playerAverages={playerAverages}
              lobbyAverages={lobbyAverages}
              deltas={deltas}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────
export default function Dashboard() {
  const { gameName: rawGameName, tagLine: rawTagLine } = useParams();
  const gameName = rawGameName ? decodeURIComponent(rawGameName) : "";
  const tagLine  = rawTagLine  ? decodeURIComponent(rawTagLine)  : "";

  const { state } = useLocation();
  const navigate = useNavigate();

  const [resolvedPuuid, setResolvedPuuid] = useState(state?.puuid ?? null);
  const [profile, setProfile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [ddVersion, setDdVersion] = useState("14.24.1");

  const [expandedMatchId, setExpandedMatchId] = useState(null);
  const [scoreboard, setScoreboard] = useState(null);
  const [scoreboardLoading, setScoreboardLoading] = useState(false);

  const MAX_GAMES = 40;
  const [extraGames, setExtraGames] = useState([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  const doFetch = async (puuidHint) => {
    const [versions, puuidResolved] = await Promise.all([
      fetch("https://ddragon.leagueoflegends.com/api/versions.json")
        .then((r) => r.json())
        .catch(() => ["14.24.1"]),
      puuidHint
        ? Promise.resolve(puuidHint)
        : getSummoner(gameName, tagLine).then((d) => d.puuid),
    ]);
    setDdVersion(versions[0]);
    setResolvedPuuid(puuidResolved);
    const [prof, anal] = await Promise.all([
      getProfile(puuidResolved),
      analyzeSummoner(puuidResolved, gameName),
    ]);
    setProfile(prof);
    setAnalysis(anal);
    setExtraGames([]);
    setHasMore(true);
  };

  useEffect(() => {
    if (!gameName || !tagLine) { navigate("/"); return; }
    setLoading(true);
    setProfile(null);
    setAnalysis(null);
    setError("");
    setExpandedMatchId(null);
    setScoreboard(null);
    doFetch(state?.puuid)
      .catch(() => setError("Failed to load data. Check that the backend is running."))
      .finally(() => setLoading(false));
  }, [gameName, tagLine]);

  const handleRefresh = () => {
    if (refreshing) return;
    setRefreshing(true);
    setExpandedMatchId(null);
    setScoreboard(null);
    doFetch(resolvedPuuid)
      .catch(() => setError("Failed to refresh."))
      .finally(() => setRefreshing(false));
  };

  const handleLoadMore = async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const start = analysis.games.length + extraGames.length;
      const remaining = MAX_GAMES - start;
      const count = Math.min(10, remaining);
      const newGames = await getHistory(resolvedPuuid, start, count);
      setExtraGames((prev) => [...prev, ...newGames]);
      if (newGames.length < count) setHasMore(false);
    } catch {
      // silently fail - button stays visible for retry
    } finally {
      setLoadingMore(false);
    }
  };

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

  if (loading) return <SkeletonDashboard />;
  if (error) return <ErrorScreen message={error} onRetry={() => navigate("/")} />;

  return (
    <div className="min-h-screen pt-20 pb-16 px-4 animate-fadeIn">
      <div className="max-w-6xl mx-auto">

        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => navigate("/")}
            className="text-xs font-semibold text-slate-400 dark:text-white/30 hover:text-[#c89b3c] dark:hover:text-[#c89b3c] transition-colors flex items-center gap-1"
          >
            ← Search Again
          </button>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 dark:text-white/30 hover:text-[#c89b3c] dark:hover:text-[#c89b3c] disabled:opacity-50 transition-colors"
          >
            {refreshing ? (
              <span className="w-3.5 h-3.5 rounded-full border-[1.5px] border-slate-300 dark:border-white/20 border-t-[#c89b3c] animate-spin block" />
            ) : (
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5c1.55 0 2.95.64 3.96 1.66" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                <path d="M11.5 1.5v3h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        <div className="flex flex-col lg:flex-row gap-5 items-start">

          {/* Left - profile + match history */}
          <div className="flex-1 min-w-0 space-y-4">

            <ProfileCard gameName={gameName} tagLine={tagLine} puuid={resolvedPuuid} profile={profile} games={analysis.games} ddVersion={ddVersion} />

            <SummaryStrip analysis={analysis} />

            {analysis.mostDiffedLane && (() => {
              const m = LANE_META[analysis.mostDiffedLane] ?? { abbr: analysis.mostDiffedLane, color: "text-slate-400", bg: "bg-slate-400/10", border: "border-slate-400/25" };
              return (
                <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${m.bg} ${m.border}`}>
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-xs font-black border flex-shrink-0 ${m.color} ${m.bg} ${m.border}`}>
                    {m.abbr}
                  </div>
                  <div className="min-w-0">
                    <div className={`text-sm font-bold ${m.color}`}>{m.abbr} was most diffed</div>
                    <div className="text-[11px] text-slate-400 dark:text-white/30">biggest score gap across your recent games</div>
                  </div>
                </div>
              );
            })()}

            {(() => {
              const allGames = [...analysis.games, ...extraGames];
              const canLoadMore = hasMore && allGames.length < MAX_GAMES;
              return (
                <div>
                  <SectionLabel>Match History</SectionLabel>
                  <div className="space-y-2">
                    {allGames.map((game) => (
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
                  {canLoadMore && (
                    <button
                      onClick={handleLoadMore}
                      disabled={loadingMore}
                      className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                        border border-slate-200 dark:border-white/[0.07]
                        bg-white dark:bg-white/[0.02]
                        text-xs font-semibold text-slate-400 dark:text-white/30
                        hover:text-[#c89b3c] hover:border-[#c89b3c]/30
                        disabled:opacity-50 transition-colors"
                    >
                      {loadingMore ? (
                        <span className="w-3.5 h-3.5 rounded-full border-[1.5px] border-slate-300 dark:border-white/20 border-t-[#c89b3c] animate-spin block" />
                      ) : null}
                      {loadingMore ? "Loading…" : `Load more · ${allGames.length} / ${MAX_GAMES}`}
                    </button>
                  )}
                  {!canLoadMore && allGames.length >= MAX_GAMES && (
                    <p className="mt-3 text-center text-[11px] text-slate-300 dark:text-white/20">
                      Showing max {MAX_GAMES} games
                    </p>
                  )}
                </div>
              );
            })()}

          </div>

          {/* Right - sticky tabbed panel */}
          <div className="w-full lg:w-80 xl:w-96 flex-shrink-0 lg:sticky lg:top-20">
            <RightPanel
              coaching={analysis.coaching}
              playerAverages={analysis.playerAverages}
              lobbyAverages={analysis.lobbyAverages}
              deltas={analysis.deltas}
              playerContext={[
                `Player: ${gameName}`,
                `Role: ${analysis.mostPlayedPosition}`,
                `Win rate (last 5): ${analysis.winRate}%`,
                `Avg KDA: ${analysis.playerAverages.kda.toFixed(2)} (lobby: ${analysis.lobbyAverages.kda.toFixed(2)})`,
                `CS/min: ${analysis.playerAverages.cspm.toFixed(2)} (lobby: ${analysis.lobbyAverages.cspm.toFixed(2)})`,
                `Vision: ${analysis.playerAverages.visionScore.toFixed(1)} (lobby: ${analysis.lobbyAverages.visionScore.toFixed(1)})`,
                `Damage: ${(analysis.playerAverages.totalDamageDealtToChampions/1000).toFixed(1)}k (lobby: ${(analysis.lobbyAverages.totalDamageDealtToChampions/1000).toFixed(1)}k)`,
                `Gold: ${(analysis.playerAverages.goldEarned/1000).toFixed(1)}k (lobby: ${(analysis.lobbyAverages.goldEarned/1000).toFixed(1)}k)`,
              ].join("\n")}
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
