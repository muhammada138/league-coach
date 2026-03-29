import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { getProfile, analyzeSummoner, getScoreboard, getHistory, getSummoner, askCoach, getLiveGame } from "../api/riot";
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
  const ch   = player.challenges || {};
  const lane = player.teamPosition || "MIDDLE";

  // Base
  const base = 15.0;

  // Global
  const gpm  = ch.goldPerMinute        ?? 0;
  const dpm  = ch.damagePerMinute      ?? 0;
  const vspm = ch.visionScorePerMinute ?? 0;
  const globalScore = (gpm + 60) * 0.008 + (dpm - 24.6) * 0.007 + vspm * 2.0;

  // KDA (role-dependent)
  const kills   = player.kills   ?? 0;
  const deaths  = player.deaths  ?? 0;
  const assists = player.assists ?? 0;
  let kdaScore;
  if (lane === "TOP") {
    kdaScore = kills * 0.80 + assists * 0.80 + deaths * -1.50;
  } else if (lane === "UTILITY") {
    kdaScore = kills * 0.85 + assists * 0.90 + deaths * -1.25;
  } else {
    kdaScore = kills * 0.75 + assists * 0.75 + deaths * -1.50;
  }

  // Lane Performance (vs lane opponent)
  let laneScore = 0.0;
  if (lane && lane !== "UNKNOWN") {
    const opp = allPlayers.find(
      (p) => p.teamPosition === lane && p.teamId !== player.teamId
    );
    if (opp) {
      const goldDiff = (player.goldEarned ?? 0) - (opp.goldEarned ?? 0);
      const xpDiff   = (player.champExperience ?? 0) - (opp.champExperience ?? 0);
      const maxCsAdv = ch.maxCsAdvantageOnLaneOpponent ?? 0;
      const rawLane  = goldDiff * 0.0015 + xpDiff * 0.0011 + maxCsAdv * 0.08;
      laneScore = Math.max(-5.0, Math.min(10.0, rawLane));
    }
  }

  // Objectives
  const riftHeralds = ch.riftHeraldKills ?? 0;
  const dragons     = player.dragonKills ?? 0;
  const barons      = player.baronKills  ?? 0;
  const horde       = ch.voidMonsterKill ?? 0;
  const objDmg      = player.damageDealtToObjectives ?? 0;
  const objScore    = riftHeralds * 3.0 + dragons * 2.1 + barons * 2.0 + horde * 0.5 + objDmg * 0.00024;

  // Team (Riot challenges values are 0-1; convert to 0-100 for the formula)
  const kpPct       = (ch.killParticipation          ?? 0) * 100;
  const teamDmgPct  = (ch.teamDamagePercentage        ?? 0) * 100;
  const dmgTakenPct = (ch.damageTakenOnTeamPercentage ?? 0) * 100;
  const teamScore   = (kpPct - 25) * 0.14 + teamDmgPct * 0.09 + dmgTakenPct * 0.07;

  // Role-Specific Mastery
  let roleSpecific;
  if (lane === "TOP" || lane === "MIDDLE" || lane === "BOTTOM") {
    // Branch A: Laners
    const laneMins     = ch.laneMinionsFirst10Minutes ?? 0;
    const turretPlates = ch.turretPlatesTaken         ?? 0;
    const soloKills    = ch.soloKills                 ?? 0;
    const turretTds    = ch.turretTakedowns           ?? 0;

    let cs10Score = 0.0;
    if (laneMins > 0 && (lane === "TOP" || lane === "MIDDLE")) {
      cs10Score = (laneMins - 54.0) * 0.35;
    } else if (laneMins > 0) { // BOTTOM
      cs10Score = (laneMins - 51.0) * 0.35;
    }
    const platesScore = 2.25 + turretPlates * 1.50;
    const soloScore = lane === "BOTTOM" ? soloKills * 1.50
                    : lane === "MIDDLE" ? soloKills * 0.85
                    : /* TOP */           soloKills * 0.75;
    const tdScore = lane === "TOP" ? turretTds * 0.85 : turretTds * 0.75;

    roleSpecific = cs10Score + platesScore + soloScore + tdScore;

  } else if (lane === "JUNGLE") {
    // Branch B: Jungle
    const initCrab   = ch.initialCrabCount        ?? 0;
    const scuttle    = ch.scuttleCrabKills         ?? 0;
    const jungleCs10 = ch.jungleCsBefore10Minutes  ?? 0;
    const enemyJg    = ch.enemyJungleMonsterKills  ?? 0;
    const pickKill   = ch.pickKillWithAlly         ?? 0;

    roleSpecific = (
      initCrab   * 1.50
      + scuttle    * 0.45
      + jungleCs10 * 0.067
      + enemyJg    * 0.50
      + pickKill   * 0.275
    );

  } else {
    // Branch C: Support (UTILITY)
    const supportQuest = ch.completeSupportQuestInTime ?? 0;
    const stealthWards = ch.stealthWardsPlaced         ?? 0;
    const controlWards = ch.controlWardsPlaced         ?? 0;
    const wardTds      = ch.wardTakedowns              ?? 0;
    const pickKill     = ch.pickKillWithAlly           ?? 0;

    const questScore = supportQuest ? 1.50 : -3.0;
    roleSpecific = (
      questScore
      + stealthWards * 0.17
      + controlWards * 0.58
      + wardTds      * 0.42
      + pickKill     * 0.22
    );
  }
  
  roleSpecific = Math.max(0.0, Math.min(20.0, roleSpecific));

  // Win/Loss
  const winLoss = player.win ? 3.0 : -3.0;

  // Total
  const total = base + globalScore + laneScore + objScore + teamScore + kdaScore + roleSpecific + winLoss;
  return Math.max(0, Math.min(100, total)).toFixed(2);
}

// LP series anchored to current LP, working backwards through games.
// games: newest-first (as returned by API). Returns length = games.length + 1.
// Index 0 = LP before oldest game shown; index N = currentLP.
function computeLPSeries(games, currentLP) {
  const ordered = [...games].reverse();
  const series = new Array(ordered.length + 1);
  series[ordered.length] = currentLP;
  for (let i = ordered.length - 1; i >= 0; i--) {
    series[i] = ordered[i].win ? series[i + 1] - 20 : series[i + 1] + 17;
  }
  return series;
}

// Aggregate teammates or opponents across all games.
// type: "with" | "against" → returns [{ puuid, name, games, wins }] sorted by games desc
function aggregateTeammates(games, type) {
  const map = {};
  games.forEach((game) => {
    const list = type === "with" ? game.teammates : game.opponents;
    if (!Array.isArray(list)) return;
    list.forEach((p) => {
      if (!p.puuid) return;
      if (!map[p.puuid]) map[p.puuid] = { puuid: p.puuid, name: p.gameName, games: 0, wins: 0 };
      map[p.puuid].games++;
      if (game.win) map[p.puuid].wins++;
    });
  });
  return Object.values(map).sort((a, b) => b.games - a.games);
}

// Module-level cache for Data Dragon champion ID → asset name
let _champIdMap = null;
async function getChampIdMap(ddVersion) {
  if (_champIdMap) return _champIdMap;
  try {
    const res = await fetch(
      `https://ddragon.leagueoflegends.com/cdn/${ddVersion}/data/en_US/champion.json`
    );
    const data = await res.json();
    _champIdMap = {};
    Object.values(data.data).forEach((c) => { _champIdMap[c.key] = c.id; });
  } catch { _champIdMap = {}; }
  return _champIdMap;
}

const QUEUE_LABELS = {
  420: "Solo/Duo Ranked", 440: "Flex Ranked",
  450: "ARAM", 400: "Normal Draft", 430: "Normal Blind",
};

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
function LPGraph({ games, profile, puuid }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);
  const currentLP = profile?.lp ?? 0;
  const rankLabel = profile?.tier === "UNRANKED" ? "Unranked" : `${profile?.tier} ${profile?.division}`;
  const ordered = [...games].reverse();

  const series = (() => {
    const storageKey = `lp_${puuid}`;
    const fingerprint = `${currentLP}:${games.map((g) => g.matchId).join(",")}`;
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) ?? "null");
      if (stored?.fingerprint === fingerprint) return stored.series;
    } catch { /* ignore */ }
    const computed = computeLPSeries(games, currentLP);
    try { localStorage.setItem(storageKey, JSON.stringify({ fingerprint, series: computed })); } catch { /* ignore */ }
    return computed;
  })();

  const min = Math.min(...series);
  const max = Math.max(...series);
  const range = Math.max(max - min, 30);
  const W = 260, H = 52, padX = 8, padY = 8;
  const innerW = W - 2 * padX, innerH = H - 2 * padY;
  const toX = (i) => padX + (i / (series.length - 1)) * innerW;
  const toY = (v) => padY + innerH - ((v - min) / range) * innerH;
  const pathD = series.map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(v).toFixed(1)}`).join(" ");
  const areaD = `${pathD} L ${toX(series.length - 1).toFixed(1)} ${(padY + innerH).toFixed(1)} L ${toX(0).toFixed(1)} ${(padY + innerH).toFixed(1)} Z`;
  const netDelta = series[series.length - 1] - series[0];
  const lineColor = netDelta >= 0 ? "#10b981" : "#ef4444";

  return (
    <div className="mt-4 pt-4 border-t border-slate-100 dark:border-white/[0.06]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-white/25">
          LP Trend · Last {games.length}
        </span>
        <span className="text-xs font-bold text-slate-700 dark:text-white/80 transition-colors duration-200">
          {hoveredIdx !== null ? `${rankLabel} · ${series[hoveredIdx]} LP` : `${rankLabel} · ${currentLP} LP`}
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
        {series.map((v, i) => {
          const cx = toX(i);
          const cy = toY(v);
          const game = i > 0 ? ordered[i - 1] : null;
          const dotColor = i === 0 ? "#475569" : game?.win ? "#10b981" : "#ef4444";
          const hovered = hoveredIdx === i;
          return (
            <g key={i} transform={`translate(${cx.toFixed(1)},${cy.toFixed(1)})`}
              onMouseEnter={() => setHoveredIdx(i)} onMouseLeave={() => setHoveredIdx(null)}>
              {/* glow ring */}
              <circle r="5" fill={dotColor}
                style={{ opacity: hovered ? 0.22 : 0, transformBox: "fill-box", transformOrigin: "center",
                  transform: hovered ? "scale(1)" : "scale(0.3)", transition: "opacity 0.18s, transform 0.18s" }} />
              {/* main dot */}
              <circle r="3" fill={dotColor}
                style={{ transformBox: "fill-box", transformOrigin: "center",
                  transform: hovered ? "scale(1.55)" : "scale(1)", transition: "transform 0.18s ease" }} />
              {/* hit area */}
              <circle r="8" fill="transparent" style={{ cursor: "default" }} />
            </g>
          );
        })}
        {hoveredIdx !== null && (() => {
          const lp = series[hoveredIdx];
          const game = hoveredIdx > 0 ? ordered[hoveredIdx - 1] : null;
          const label = game ? `${rankLabel} · ${lp} LP · ${game.win ? "W" : "L"}` : `${rankLabel} · ${lp} LP`;
          const cx = toX(hoveredIdx);
          const cy = toY(lp);
          const tw = label.length * 7 + 14;
          const th = 20;
          const tx = Math.min(Math.max(cx - tw / 2, 2), W - tw - 2);
          const ty = Math.max(cy - th - 7, 2);
          return (
            <g style={{ pointerEvents: "none" }}>
              <rect x={tx} y={ty} width={tw} height={th} rx={3} ry={3} fill="#0f172a" fillOpacity={0.93} />
              <text x={tx + tw / 2} y={ty + 14} textAnchor="middle" fill="white"
                style={{ fontSize: "11px", fontWeight: 700, fontFamily: "inherit" }}>
                {label}
              </text>
            </g>
          );
        })()}
      </svg>
      <div className="flex justify-between text-[10px] text-slate-400 dark:text-white/20 mt-0.5">
        <span>{games.length} games ago</span>
        <span>Now · {currentLP} LP</span>
      </div>
    </div>
  );
}

// ── Star / save button ─────────────────────────────────────────────────────
function StarButton({ gameName, tagLine, puuid, profileIconId }) {
  const [saved, setSaved] = useState(() =>
    readSaved().some((p) => p.puuid === puuid)
  );

  if (!tagLine || !puuid) return null;

  const toggle = () => {
    const current = readSaved();
    if (saved) {
      writeSaved(current.filter((p) => p.puuid !== puuid));
      setSaved(false);
    } else {
      if (current.length >= 10) return;
      writeSaved([...current, { gameName, tagLine, puuid, profileIconId }]);
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

// ── Live Game Banner ────────────────────────────────────────────────────────
function LiveGameBanner({ liveGame, ddVersion, puuid, onClose }) {
  const [champMap, setChampMap] = useState(null);
  const [elapsed, setElapsed] = useState(liveGame.gameLength ?? 0);

  useEffect(() => { getChampIdMap(ddVersion).then(setChampMap); }, [ddVersion]);
  useEffect(() => {
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const mins = Math.floor(elapsed / 60);
  const secs = String(elapsed % 60).padStart(2, "0");
  const queueLabel = QUEUE_LABELS[liveGame.queueId] ?? liveGame.gameMode ?? "Live Game";
  const blueTeam = liveGame.participants.filter((p) => p.teamId === 100);
  const redTeam  = liveGame.participants.filter((p) => p.teamId === 200);

  const renderPlayer = (p) => {
    const isMe = p.puuid === puuid;
    const champName = champMap ? (champMap[String(p.championId)] ?? null) : null;
    const iconUrl = champName
      ? `https://ddragon.leagueoflegends.com/cdn/${ddVersion}/img/champion/${champName}.png`
      : null;
    return (
      <div key={p.puuid || p.summonerName}
        className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg transition-colors
          ${isMe ? "bg-[#c89b3c]/10 border border-[#c89b3c]/20" : "hover:bg-slate-50 dark:hover:bg-white/[0.02]"}`}
      >
        {iconUrl ? (
          <img src={iconUrl} alt={champName}
            className="w-7 h-7 rounded object-cover border border-slate-200 dark:border-white/10 flex-shrink-0"
            onError={(e) => { e.target.style.display = "none"; }} />
        ) : (
          <div className="w-7 h-7 rounded bg-slate-200 dark:bg-white/10 flex-shrink-0 animate-pulse" />
        )}
        <span className={`text-xs font-semibold truncate ${isMe ? "text-[#c89b3c]" : "text-slate-700 dark:text-white/70"}`}>
          {isMe && "★ "}{p.summonerName}
          <span className="text-slate-400 dark:text-white/30 font-normal">{p.tagLine ? `#${p.tagLine}` : ""}</span>
        </span>
      </div>
    );
  };

  return (
    <div className="bg-white dark:bg-white/[0.03] border border-red-200 dark:border-red-500/20 rounded-2xl shadow-sm dark:shadow-black/40 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-red-50/60 dark:bg-red-950/20 border-b border-red-100 dark:border-red-500/10">
        <div className="flex items-center gap-2.5">
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-500 text-white text-[10px] font-black tracking-widest">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            LIVE
          </span>
          <span className="text-sm font-bold text-slate-800 dark:text-white tabular-nums">{mins}:{secs}</span>
          <span className="text-xs text-slate-400 dark:text-white/30">{queueLabel}</span>
        </div>
        <button onClick={onClose} className="text-slate-400 dark:text-white/20 hover:text-slate-600 dark:hover:text-white/50 transition-colors">
          <svg className="w-4 h-4" viewBox="0 0 12 12" fill="none">
            <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <div className="p-3 grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-1.5 px-1">Blue Team</div>
          <div className="space-y-0.5">{blueTeam.map(renderPlayer)}</div>
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-red-400 mb-1.5 px-1">Red Team</div>
          <div className="space-y-0.5">{redTeam.map(renderPlayer)}</div>
        </div>
      </div>
    </div>
  );
}

// ── Profile Card ───────────────────────────────────────────────────────────
function ProfileCard({ gameName, tagLine, puuid, profile, games, ddVersion, onLiveCheck, liveLoading }) {
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
          <div className="flex items-center gap-0.5 mb-0.5 flex-wrap">
            <h2 className="text-lg font-extrabold text-slate-900 dark:text-white tracking-tight leading-none truncate">
              {gameName}
            </h2>
            <span className="text-xs text-slate-400 dark:text-white/25 font-normal ml-1 flex-shrink-0">
              #{tagLine}
            </span>
            <StarButton gameName={gameName} tagLine={tagLine} puuid={puuid} profileIconId={profile.profileIconId} />
            {onLiveCheck && (
              <button
                onClick={onLiveCheck}
                disabled={liveLoading}
                className="ml-2 flex-shrink-0 flex items-center gap-1 text-[10px] font-bold
                  px-2 py-0.5 rounded border border-red-400/40 text-red-400
                  hover:bg-red-400/10 transition-colors disabled:opacity-50"
              >
                {liveLoading
                  ? <span className="w-2 h-2 rounded-full border border-t-red-400 border-red-400/20 animate-spin block" />
                  : <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />}
                LIVE
              </button>
            )}
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
      {games && <LPGraph games={games} profile={profile} puuid={puuid} />}
    </div>
  );
}

// ── Expanded Scoreboard ────────────────────────────────────────────────────
function TeamScoreRows({ players, isWin, teamLabel, gameName, isRemake }) {
  const navigate = useNavigate();
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
        const scoreNum = isRemake ? 0 : parseFloat(p.score);
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
                <button
                  onClick={() => p.puuid && p.riotIdTagline && navigate(
                    `/player/${encodeURIComponent(p.riotIdGameName)}/${encodeURIComponent(p.riotIdTagline)}`,
                    { state: { puuid: p.puuid } }
                  )}
                  disabled={!p.puuid || !p.riotIdTagline}
                  className={`font-semibold truncate max-w-[110px] text-xs text-left
                    ${isMe ? "text-[#c89b3c]" : "text-slate-700 dark:text-white/70"}
                    ${p.puuid && p.riotIdTagline ? "hover:underline hover:text-[#c89b3c] cursor-pointer" : "cursor-default"}`}
                >
                  {isMe && "★ "}{p.riotIdGameName || "Unknown"}
                </button>
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
              <span className={`font-bold text-sm ${scoreColor}`}>{Math.round(scoreNum)}</span>
            </td>
          </tr>
        );
      })}
    </>
  );
}

function ExpandedScoreboard({ scoreboard, loading, gameName, isRemake }) {
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
    score: p.score ?? computePerformanceScore(p, scoreboard),
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
            isRemake={isRemake}
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
            isRemake={isRemake}
          />
        </tbody>
      </table>
    </div>
  );
}

// ── Horizontal Game Row ────────────────────────────────────────────────────
function GameRow({ game, isExpanded, onToggle, scoreboard, scoreboardLoading, gameName }) {
  const isRemake = game.gameDuration < 210;
  const mins = Math.floor(game.gameDuration / 60);
  const secs = String(game.gameDuration % 60).padStart(2, "0");
  const imgSrc = `https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/${game.championName}.png`;
  const kda = ((game.kills + game.assists) / Math.max(game.deaths, 1)).toFixed(2);
  const scoreColor = game.score >= 79
    ? "text-emerald-500 dark:text-emerald-400"
    : game.score >= 50
    ? "text-[#c89b3c]"
    : "text-slate-400 dark:text-white/40";

  const borderClass = isRemake
    ? "border-slate-300 dark:border-white/10"
    : game.win
    ? "border-emerald-200 dark:border-emerald-500/25"
    : "border-red-200 dark:border-red-500/25";

  const bgClass = isRemake
    ? "bg-slate-100/70 dark:bg-slate-800/20 hover:bg-slate-100 dark:hover:bg-slate-800/30"
    : game.win
    ? "bg-emerald-50/70 dark:bg-emerald-950/25 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
    : "bg-red-50/70 dark:bg-red-950/25 hover:bg-red-50 dark:hover:bg-red-950/40";

  const accentClass = isRemake ? "bg-slate-400/50" : game.win ? "bg-emerald-400" : "bg-red-400";

  return (
    <div
      className={`rounded-xl overflow-hidden border transition-all duration-300
        ${borderClass}
        ${isExpanded ? "ring-1 ring-[#c89b3c]/40 shadow-lg shadow-[#c89b3c]/5" : ""}`}
    >
      {/* Clickable header */}
      <div
        className={`flex items-center gap-3 px-4 py-3 cursor-pointer select-none transition-colors duration-200 ${bgClass}`}
        onClick={onToggle}
      >
        {/* Left accent bar */}
        <div className={`w-1 h-12 rounded-full flex-shrink-0 ${accentClass}`} />

        {/* Champion icon */}
        <img
          src={imgSrc}
          alt={game.championName}
          onError={(e) => { e.target.style.display = "none"; }}
          className="w-12 h-12 rounded-lg object-cover border border-slate-200 dark:border-white/10 flex-shrink-0"
        />

        {/* Champion + result */}
        <div className="w-36 flex-shrink-0 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-bold text-slate-900 dark:text-white text-sm truncate">{game.championName}</span>
            {isRemake ? (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 bg-slate-200 dark:bg-white/10 text-slate-500 dark:text-white/40">
                Remake
              </span>
            ) : (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${
                game.win
                  ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                  : "bg-red-100 dark:bg-red-500/20 text-red-500 dark:text-red-400"
              }`}>
                {game.win ? "W" : "L"}
              </span>
            )}
            {!isRemake && game.mvpAce === "MVP" && (
              <span className="text-[10px] font-black px-1.5 py-0.5 rounded flex-shrink-0 bg-yellow-400/15 text-yellow-400 border border-yellow-400/30">
                MVP
              </span>
            )}
            {!isRemake && game.mvpAce === "ACE" && (
              <span className="text-[10px] font-black px-1.5 py-0.5 rounded flex-shrink-0 bg-orange-500/15 text-orange-400 border border-orange-400/30">
                ACE
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[11px] text-slate-400 dark:text-white/30">
              <span className="font-bold">{game.teamPosition || "-"}</span> · {mins}:{secs}
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
        {!isRemake && game.score != null && (
          <div className="flex flex-col items-center flex-shrink-0">
            <span className={`text-sm font-black tabular-nums ${scoreColor}`}>{Math.round(game.score)}</span>
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
          isRemake
            ? "border-slate-200 dark:border-white/10 bg-slate-50/20 dark:bg-slate-800/10"
            : game.win
            ? "border-emerald-200 dark:border-emerald-500/20 bg-emerald-50/20 dark:bg-emerald-950/10"
            : "border-red-200 dark:border-red-500/20 bg-red-50/20 dark:bg-red-950/10"
        }`}>
          <ExpandedScoreboard 
            scoreboard={scoreboard} 
            loading={scoreboardLoading} 
            gameName={gameName} 
            isRemake={isRemake} 
          />
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
function SummaryStrip({ analysis, games }) {
  const allGames = games || analysis.games;
  const n = allGames.length || 1;
  
  const wins = allGames.filter((g) => g.win && g.gameDuration >= 210).length;
  const losses = allGames.filter((g) => !g.win && g.gameDuration >= 210).length;
  const totalValid = wins + losses || 1;
  const winRate = ((wins / totalValid) * 100).toFixed(1);

  const tk = allGames.reduce((sum, g) => sum + g.kills, 0);
  const td = allGames.reduce((sum, g) => sum + g.deaths, 0);
  const ta = allGames.reduce((sum, g) => sum + g.assists, 0);
  const avgKda = (tk + ta) / Math.max(td, 1);

  let totalMins = 0;
  let totalCS = 0;
  let totalVision = 0;
  let totalScore = 0;
  let validScoreCount = 0;

  allGames.forEach((g) => {
    const mins = g.gameDuration / 60;
    totalMins += mins;
    totalCS += g.cspm * mins;
    totalVision += g.visionScore;
    if (g.gameDuration >= 210) {
      totalScore += g.score ?? 0;
      validScoreCount++;
    }
  });

  const avgCspm = totalMins > 0 ? totalCS / totalMins : 0;
  const avgVision = totalVision / n;
  const avgScore = validScoreCount > 0 ? totalScore / validScoreCount : 0;

  const lKda = analysis.lobbyAverages.kda;
  const lCspm = analysis.lobbyAverages.cspm;
  const lVis = analysis.lobbyAverages.visionScore;

  const items = [
    { label: "Win Rate",  value: `${winRate}%`,       sub: `${wins}W · ${losses}L`,          positive: Number(winRate) >= 50 },
    { label: "Avg KDA",   value: avgKda.toFixed(2),   sub: `Lobby ${lKda.toFixed(2)}`,       positive: avgKda >= lKda },
    { label: "CS / min",  value: avgCspm.toFixed(2),  sub: `Lobby ${lCspm.toFixed(2)}`,      positive: avgCspm >= lCspm },
    { label: "Vision",    value: avgVision.toFixed(1),sub: `Lobby ${lVis.toFixed(1)}`,       positive: avgVision >= lVis },
    { label: "Avg Score", value: avgScore.toFixed(0), sub: `Last ${validScoreCount} games`,  positive: avgScore >= 60 },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {items.map(({ label, value, sub, positive }) => (
        <div key={label} className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-xl p-3 text-center">
          <div className={`text-xl font-black tabular-nums ${positive ? "text-emerald-500" : "text-red-400"}`}>{value}</div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25 mt-0.5">{label}</div>
          <div className="text-[10px] text-slate-400 dark:text-white/20 mt-0.5">{sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Teammates Content ───────────────────────────────────────────────────────
function TeammatesContent({ games }) {
  const [tab, setTab] = useState("with");
  const rows = aggregateTeammates(games, tab).filter((r) => r.games > 1);
  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-slate-100 dark:border-white/[0.06] flex-shrink-0 mx-5 mb-1 mt-3">
        {["with", "against"].map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-semibold capitalize transition-colors duration-150
              ${tab === t
                ? "text-slate-900 dark:text-white border-b-2 border-[#c89b3c] -mb-px"
                : "text-slate-400 dark:text-white/30 hover:text-slate-600 dark:hover:text-white/50"}`}
          >
            {t === "with" ? "With" : "Against"}
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-slate-400 dark:text-white/25 text-center px-5">
            No repeat {tab === "with" ? "teammates" : "opponents"} yet — load more games to find patterns.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-3 px-5 py-1.5">
            {["Summoner", "G", "W/L", "WR"].map((h, i) => (
              <span key={h} className={`text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-white/25 ${i > 0 ? "text-right" : ""}`}>{h}</span>
            ))}
          </div>
          <div className="overflow-y-auto flex-1">
            {rows.map((r) => {
              const wr = r.games > 0 ? Math.round((r.wins / r.games) * 100) : 0;
              const wrColor = wr >= 55 ? "text-emerald-500 dark:text-emerald-400" : wr >= 45 ? "text-slate-600 dark:text-white/60" : "text-red-400";
              return (
                <div key={r.puuid} className="grid grid-cols-[1fr_auto_auto_auto] gap-x-3 px-5 py-2
                  hover:bg-slate-50 dark:hover:bg-white/[0.02] transition-colors border-b
                  border-slate-50 dark:border-white/[0.03] last:border-0">
                  <span className="text-xs font-semibold text-slate-700 dark:text-white/70 truncate max-w-[130px]">{r.name}</span>
                  <span className="text-xs text-slate-500 dark:text-white/40 text-right tabular-nums">{r.games}</span>
                  <span className="text-xs text-slate-500 dark:text-white/40 text-right tabular-nums whitespace-nowrap">{r.wins}-{r.games - r.wins}</span>
                  <span className={`text-xs font-bold text-right tabular-nums ${wrColor}`}>{wr}%</span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── Right Panel (tabbed: Coaching | Stats | Teams) ──────────────────────────
function RightPanel({ coaching, playerAverages, lobbyAverages, deltas, playerContext, games }) {
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
    if (chatHistory.length > 0 || chatLoading) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [chatHistory, chatLoading]);

  return (
    <div className="bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-2xl shadow-sm dark:shadow-black/40 flex flex-col lg:max-h-[calc(100vh-5.5rem)] lg:overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-slate-100 dark:border-white/[0.06] flex-shrink-0">
        {[
          { id: "coaching", label: "AI Coaching", dot: true },
          { id: "stats",    label: "Stats",        dot: false },
          { id: "teams",    label: "Teams",        dot: false },
        ].map(({ id, label, dot }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-3.5 text-xs font-semibold tracking-wide transition-colors duration-150
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
            {/* Single unified scroll area: tips + chat together */}
            <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-4">
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

              {chatHistory.length > 0 && (
                <div className="border-t border-slate-100 dark:border-white/[0.06] pt-4 space-y-3">
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
            </div>

            {/* Fixed input bar */}
            <div className="border-t border-slate-100 dark:border-white/[0.06] flex-shrink-0">
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
        ) : tab === "stats" ? (
          <div className="lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
            <StatsContent
              playerAverages={playerAverages}
              lobbyAverages={lobbyAverages}
              deltas={deltas}
            />
          </div>
        ) : (
          <div className="lg:flex-1 lg:min-h-0 lg:overflow-hidden lg:flex lg:flex-col">
            <TeammatesContent games={games} />
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

  const [liveGame, setLiveGame] = useState(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [notInGame, setNotInGame] = useState(false);

  const MAX_GAMES = 40;
  const [extraGames, setExtraGames] = useState([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  const [queueTab, setQueueTab] = useState("ranked");
  const [tabGames, setTabGames] = useState({ flex: null, draft: null });
  const [tabHasMore, setTabHasMore] = useState({ flex: true, draft: true });
  const [tabLoadingMore, setTabLoadingMore] = useState(false);

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
    setQueueTab("ranked");
    setTabGames({ flex: null, draft: null });
    setTabHasMore({ flex: true, draft: true });
  };

  useEffect(() => {
    if (!gameName || !tagLine) { navigate("/"); return; }
    window.scrollTo(0, 0);
    setLoading(true);
    setProfile(null);
    setAnalysis(null);
    setError("");
    setExpandedMatchId(null);
    setScoreboard(null);
    setLiveGame(null);
    setNotInGame(false);
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
    if (queueTab === "ranked") {
      if (loadingMore || !hasMore) return;
      setLoadingMore(true);
      try {
        const start = analysis.games.length + extraGames.length;
        const remaining = MAX_GAMES - start;
        const count = Math.min(10, remaining);
        const newGames = await getHistory(resolvedPuuid, start, count, 420);
        setExtraGames((prev) => [...prev, ...newGames]);
        if (newGames.length < count) setHasMore(false);
      } catch {
        // silently fail
      } finally {
        setLoadingMore(false);
      }
    } else {
      if (tabLoadingMore || !tabHasMore[queueTab]) return;
      const queueNum = queueTab === "flex" ? 440 : 400;
      const currentGames = tabGames[queueTab] ?? [];
      setTabLoadingMore(true);
      try {
        const start = currentGames.length;
        const remaining = MAX_GAMES - start;
        const count = Math.min(10, remaining);
        const newGames = await getHistory(resolvedPuuid, start, count, queueNum);
        setTabGames((prev) => ({ ...prev, [queueTab]: [...currentGames, ...newGames] }));
        if (newGames.length < count) setTabHasMore((prev) => ({ ...prev, [queueTab]: false }));
      } catch {
        // silently fail
      } finally {
        setTabLoadingMore(false);
      }
    }
  };

  const handleQueueTabChange = async (tabId) => {
    setQueueTab(tabId);
    if (tabId !== "ranked" && tabGames[tabId] === null) {
      const queueNum = tabId === "flex" ? 440 : 400;
      setTabLoadingMore(true);
      try {
        const games = await getHistory(resolvedPuuid, 0, 10, queueNum);
        setTabGames((prev) => ({ ...prev, [tabId]: games }));
        if (games.length < 10) setTabHasMore((prev) => ({ ...prev, [tabId]: false }));
      } catch {
        setTabGames((prev) => ({ ...prev, [tabId]: [] }));
      } finally {
        setTabLoadingMore(false);
      }
    }
  };

  const handleLiveCheck = async () => {
    if (liveLoading || !resolvedPuuid) return;
    setLiveLoading(true);
    try {
      const data = await getLiveGame(resolvedPuuid);
      if (data.inGame) {
        setLiveGame(data);
      } else {
        setLiveGame(null);
        setNotInGame(true);
        setTimeout(() => setNotInGame(false), 2500);
      }
    } catch { /* silently fail */ } finally {
      setLiveLoading(false);
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

            <ProfileCard
              gameName={gameName}
              tagLine={tagLine}
              puuid={resolvedPuuid}
              profile={profile}
              games={[...analysis.games, ...extraGames]}
              ddVersion={ddVersion}
              onLiveCheck={handleLiveCheck}
              liveLoading={liveLoading}
            />

            {liveGame?.inGame && (
              <LiveGameBanner
                liveGame={liveGame}
                ddVersion={ddVersion}
                puuid={resolvedPuuid}
                onClose={() => setLiveGame(null)}
              />
            )}
            {notInGame && (
              <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.07] text-xs text-slate-500 dark:text-white/40 animate-fadeIn">
                <svg className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M8 5v4M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                Not currently in a game
              </div>
            )}

            <SummaryStrip analysis={analysis} games={[...analysis.games, ...extraGames]} />

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
              const allRankedGames = [...analysis.games, ...extraGames];
              const currentGames = queueTab === "ranked" ? allRankedGames : (tabGames[queueTab] ?? []);
              const currentLoading = queueTab === "ranked" ? loadingMore : tabLoadingMore;
              const currentHasMore = queueTab === "ranked"
                ? hasMore && allRankedGames.length < MAX_GAMES
                : tabHasMore[queueTab] && currentGames.length < MAX_GAMES;
              const isInitialTabLoad = queueTab !== "ranked" && tabGames[queueTab] === null && tabLoadingMore;
              const QUEUE_TAB_OPTIONS = [
                { id: "ranked", label: "Solo/Duo" },
                { id: "flex",   label: "Flex" },
                { id: "draft",  label: "Draft" },
              ];
              return (
                <div>
                  <SectionLabel>Match History</SectionLabel>
                  <div className="flex gap-1 mb-3">
                    {QUEUE_TAB_OPTIONS.map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => handleQueueTabChange(id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors
                          ${queueTab === id
                            ? "bg-[#c89b3c]/15 text-[#c89b3c] border border-[#c89b3c]/30"
                            : "text-slate-400 dark:text-white/30 border border-transparent hover:border-slate-200 dark:hover:border-white/10 hover:text-slate-600 dark:hover:text-white/50"
                          }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {isInitialTabLoad ? (
                    <div className="flex items-center justify-center py-8 gap-3">
                      <div className="w-4 h-4 rounded-full border-2 border-t-[#c89b3c] border-[#c89b3c]/20 animate-spin" />
                      <span className="text-sm text-slate-400 dark:text-white/30">Loading…</span>
                    </div>
                  ) : currentGames.length === 0 ? (
                    <div className="py-8 text-center text-sm text-slate-400 dark:text-white/30">
                      No {queueTab === "flex" ? "Flex Ranked" : "Normal Draft"} games found
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {currentGames.map((game) => (
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
                  )}
                  {!isInitialTabLoad && currentHasMore && currentGames.length > 0 && (
                    <button
                      onClick={handleLoadMore}
                      disabled={currentLoading}
                      className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                        border border-slate-200 dark:border-white/[0.07]
                        bg-white dark:bg-white/[0.02]
                        text-xs font-semibold text-slate-400 dark:text-white/30
                        hover:text-[#c89b3c] hover:border-[#c89b3c]/30
                        disabled:opacity-50 transition-colors"
                    >
                      {currentLoading ? (
                        <span className="w-3.5 h-3.5 rounded-full border-[1.5px] border-slate-300 dark:border-white/20 border-t-[#c89b3c] animate-spin block" />
                      ) : null}
                      {currentLoading ? "Loading…" : `Load more · ${currentGames.length} / ${MAX_GAMES}`}
                    </button>
                  )}
                  {!isInitialTabLoad && !currentHasMore && currentGames.length >= MAX_GAMES && (
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
              games={[...analysis.games, ...extraGames]}
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
