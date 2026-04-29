import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { getAdminDataSummary, syncMeta, cancelSync, toggleSyncPause, cleanupData, retrainModel, toggleIngest, getAvailablePatches } from "../api/riot";
import StatCard from "../components/admin/StatCard";
import MatchupTable from "../components/admin/MatchupTable";
import TierListTable from "../components/admin/TierListTable";

function fmt(n) { return n?.toLocaleString() ?? "0"; }

const TIER_ORDER = { "S+": 0, S: 1, "S-": 2, "A+": 3, A: 4, "A-": 5, "B+": 6, B: 7, "B-": 8, "C+": 9, C: 10, "C-": 11, "D+": 12, D: 13, "D-": 14, "N/A": 15 };

const ROLES = [
  { key: "all", label: "All", icon: null },
  { key: "top", label: "Top", icon: "top" },
  { key: "jungle", label: "Jng", icon: "jungle" },
  { key: "middle", label: "Mid", icon: "middle" },
  { key: "bottom", label: "Bot", icon: "bottom" },
  { key: "support", label: "Sup", icon: "utility" },
];

const RANK_ICONS = {
  bronze: "🥉", silver: "⬜", gold: "🥇", platinum: "💎", emerald: "💚", diamond: "🔷", master: "👑"
};

function RoleIcon({ icon, size = 16, active }) {
  if (!icon) return null;
  return (
    <img
      src={`https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/svg/position-${icon}.svg`}
      alt="" width={size} height={size}
      className={`inline-block transition-all duration-150 ${active ? 'opacity-100 brightness-125' : 'opacity-40 group-hover:opacity-70'}`}
      onError={e => e.target.style.display = 'none'}
    />
  );
}

export default function AdminData() {
  const [data, setData] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [paused, setPaused] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [error, setError] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedRank, setSelectedRank] = useState(searchParams.get("rank") || "emerald");
  const [selectedRole, setSelectedRole] = useState(searchParams.get("role") || "all");
  const [isAdmin, setIsAdmin] = useState(!!localStorage.getItem("admin_token"));
  const [search, setSearch] = useState("");
  const [selectedChamp, setSelectedChamp] = useState(searchParams.get("champ") || null);
  const [showAll, setShowAll] = useState(false);

  // Patch selector state — only current + previous
  const [availablePatches, setAvailablePatches] = useState([]);
  const [savedPatches, setSavedPatches] = useState([]);
  const [tierlistPatch, setTierlistPatch] = useState("");
  const [matchupPatch, setMatchupPatch] = useState("");

  useEffect(() => {
    const params = {};
    if (selectedRank !== "emerald") params.rank = selectedRank;
    if (selectedRole !== "all") params.role = selectedRole;
    if (selectedChamp) params.champ = selectedChamp;
    setSearchParams(params, { replace: true });
  }, [selectedRank, selectedRole, selectedChamp]);

  const [sortConfig, setSortConfig] = useState({ key: 'rank_num', direction: 'asc' });

  const fetchData = async () => {
    try {
      const summary = await getAdminDataSummary();
      setData(summary);
      setError("");
      setSyncing(summary?.meta?.active || false);
      setPaused(summary?.meta?.paused || false);
      if (summary?.meta?.ranks?.length > 0 && !summary.meta.ranks.includes(selectedRank)) {
        setSelectedRank(summary.meta.ranks.includes("emerald") ? "emerald" : summary.meta.ranks[0]);
      }
    } catch (err) {
      console.error(err);
      setError("Backend unreachable.");
    }
  };

  useEffect(() => {
    fetchData();
    getAvailablePatches().then(res => {
      // Only show current + previous patch (first 2)
      const patches = (res.ddragon || []).slice(0, 2);
      setAvailablePatches(patches);
      setSavedPatches(res.saved || []);
      if (patches.length >= 2) { setTierlistPatch(patches[0]); setMatchupPatch(patches[1]); }
      else if (patches.length === 1) { setTierlistPatch(patches[0]); setMatchupPatch(patches[0]); }
    }).catch(() => {});
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleLogin = () => { const p = prompt("Enter Admin API Key:"); if (p) { localStorage.setItem("admin_token", p); setIsAdmin(true); fetchData(); } };
  const handleLogout = () => { localStorage.removeItem("admin_token"); setIsAdmin(false); };

  const handleSyncMeta = async (mode = "full") => {
    if (syncing) return;
    setSyncing(true); setError("");
    try { await syncMeta(mode, tierlistPatch || null, matchupPatch || null); }
    catch (err) { setError("Sync failed: " + (err.response?.data?.detail || err.message)); setSyncing(false); }
  };
  const handleCancelSync = async () => { try { const r = await cancelSync(); if (!r.ok) throw new Error(r.message); } catch (e) { setError("Cancel failed: " + e.message); } };
  const handleTogglePause = async () => { try { const r = await toggleSyncPause(); setPaused(r.paused); } catch { setError("Pause failed."); } };

  const handleCleanup = async () => {
    if (!confirm("Run maintenance? (Prunes LP history >30 days)")) return;
    setCleaning(true);
    try { const r = await cleanupData(); alert(`Pruned ${r.counts.lp_history} entries.`); fetchData(); }
    catch { setError("Cleanup failed."); }
    finally { setCleaning(false); }
  };
  const handleRetrain = async () => {
    setRetraining(true);
    try { const r = await retrainModel(); alert(r.ok ? `Retrained! Acc: ${(r.test_accuracy * 100).toFixed(1)}%` : "Failed: " + r.error); }
    catch { setError("Retrain failed."); }
    finally { setRetraining(false); fetchData(); }
  };
  const handleToggleIngest = async () => { try { await toggleIngest(); fetchData(); } catch { setError("Toggle failed."); } };

  const rankData = useMemo(() => data?.meta?.details?.[selectedRank] || { champions: {}, tier_avg: 50 }, [data, selectedRank]);

  const champions = useMemo(() => {
    return Object.entries(rankData.champions)
      .filter(([, info]) => { const lane = info.lane || "all"; return selectedRole === "all" ? lane === "all" : lane === selectedRole; })
      .map(([key, info]) => ({
        id: key, cid: info.cid, ...info,
        name: info.name || data?.champ_names?.[info.cid] || "Unknown",
        display_lane: info.real_lane || info.lane || "unknown",
        tier_val: TIER_ORDER[info.tier] ?? 15,
        rank_num: info.rank_label && info.rank_label !== "N/A" ? parseInt(info.rank_label) : 999
      }));
  }, [rankData, data, selectedRole]);

  useEffect(() => { setSortConfig(selectedChamp ? { key: 'wr', direction: 'desc' } : { key: 'rank_num', direction: 'asc' }); }, [selectedChamp]);

  const requestSort = (key) => {
    let direction = 'desc';
    if (sortConfig.key === key && sortConfig.direction === 'desc') direction = 'asc';
    if ((key === 'tier_val' || key === 'rank_num') && sortConfig.key === key) direction = sortConfig.direction === 'asc' ? 'desc' : 'asc';
    else if (key === 'tier_val' || key === 'rank_num') direction = 'asc';
    setSortConfig({ key, direction });
  };

  const processedChamps = useMemo(() => {
    let list = [...champions];
    if (search) { const s = search.toLowerCase(); list = list.filter(c => c.name.toLowerCase().includes(s)); }
    // "Show All" toggle: filter out <0.5% pick rate champions (approx games < 200)
    if (!showAll) { const totalGames = list.reduce((acc, c) => acc + (c.games || 0), 0); if (totalGames > 0) list = list.filter(c => (c.games / totalGames) >= 0.005); }
    return list.sort((a, b) => {
      let aV = a[sortConfig.key] ?? 0, bV = b[sortConfig.key] ?? 0;
      if (typeof aV === 'string') aV = aV.toLowerCase();
      if (typeof bV === 'string') bV = bV.toLowerCase();
      return aV < bV ? (sortConfig.direction === 'asc' ? -1 : 1) : aV > bV ? (sortConfig.direction === 'asc' ? 1 : -1) : 0;
    });
  }, [champions, search, sortConfig, showAll]);

  const selectedChampData = selectedChamp ? rankData.champions[selectedChamp] : null;
  const selectedChampName = selectedChampData?.name || data?.champ_names?.[selectedChampData?.cid || selectedChamp] || "Champion";
  const matchupData = useMemo(() => {
    if (!selectedChampData?.matchups) return [];
    return Object.entries(selectedChampData.matchups).map(([opp_cid, raw]) => {
      const wr = typeof raw === "object" ? raw.wr : raw;
      const games = typeof raw === "object" ? raw.games : null;
      return { id: opp_cid, name: data?.champ_names?.[opp_cid] || "Unknown", wr, games, delta: wr - 50.0 };
    }).sort((a, b) => {
      const key = ['wr', 'name', 'games', 'delta'].includes(sortConfig.key) ? sortConfig.key : 'wr';
      let aV = a[key] ?? 0, bV = b[key] ?? 0;
      if (typeof aV === 'string') { aV = aV.toLowerCase(); bV = bV.toLowerCase(); }
      return aV < bV ? (sortConfig.direction === 'asc' ? -1 : 1) : aV > bV ? (sortConfig.direction === 'asc' ? 1 : -1) : 0;
    });
  }, [selectedChampData, data, sortConfig]);

  if (!data && !error) return (
    <div className="min-h-screen flex items-center justify-center bg-white dark:bg-[#0a0e1a]">
      <span className="w-10 h-10 border-3 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
    </div>
  );

  // Shared patch selector component used in both control panel and explorer
  const PatchSelector = ({ compact }) => (
    <div className={`flex items-center ${compact ? 'gap-4' : 'gap-5'}`}>
      <div className="flex items-center gap-2">
        <label className="text-[9px] font-bold uppercase tracking-wider text-slate-400 dark:text-white/25">Tierlist</label>
        <select value={tierlistPatch} onChange={e => setTierlistPatch(e.target.value)}
          className="bg-white dark:bg-[#0d1220] border border-slate-200 dark:border-white/10 rounded px-2.5 py-1 text-xs text-slate-800 dark:text-white/80 focus:outline-none focus:border-blue-500/50 transition-all cursor-pointer">
          {availablePatches.map(p => <option key={p} value={p}>{p}{savedPatches.includes(p) ? ' ✓' : ''}</option>)}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <label className="text-[9px] font-bold uppercase tracking-wider text-slate-400 dark:text-white/25">Matchup</label>
        <select value={matchupPatch} onChange={e => setMatchupPatch(e.target.value)}
          className="bg-white dark:bg-[#0d1220] border border-slate-200 dark:border-white/10 rounded px-2.5 py-1 text-xs text-slate-800 dark:text-white/80 focus:outline-none focus:border-blue-500/50 transition-all cursor-pointer">
          {availablePatches.map(p => <option key={p} value={p}>{p}{savedPatches.includes(p) ? ' ✓' : ''}</option>)}
        </select>
      </div>
      {savedPatches.length > 0 && !compact && (
        <span className="text-[9px] font-medium text-slate-300 dark:text-white/10">Cached: {savedPatches.join(", ")}</span>
      )}
    </div>
  );

  return (
    <div className="min-h-screen pt-24 pb-20 px-6 bg-slate-50 dark:bg-[#0a0e1a] text-slate-900 dark:text-white transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto">

        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-8">
          <StatCard title="Training Pool" value={fmt(data?.training?.match_count)} label="Matches" color="#3b82f6">
            <button onClick={handleRetrain} disabled={retraining}
              className="mt-3 w-full bg-blue-500/5 dark:bg-white/5 border border-blue-500/20 dark:border-white/10 rounded py-1.5 hover:bg-blue-500/10 dark:hover:bg-white/10 transition-all text-[9px] font-bold uppercase tracking-wider text-blue-500/70 dark:text-blue-400/60 hover:text-blue-500 dark:hover:text-blue-400">
              {retraining ? "Training..." : "Retrain Model"}
            </button>
          </StatCard>
          <StatCard title="Champions" value={data?.meta?.champion_count} label="In Database" color="#8b5cf6" />
          <StatCard title="Ingestion" value={data?.ingestion?.is_paused ? "Paused" : "Active"} label="Worker" color="#10b981">
            <button onClick={handleToggleIngest}
              className={`mt-3 w-full rounded py-1.5 transition-all text-[9px] font-bold uppercase tracking-wider border ${data?.ingestion?.is_paused ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-500/70 hover:bg-emerald-500/10 hover:text-emerald-500' : 'border-rose-500/20 bg-rose-500/5 text-rose-500/70 hover:bg-rose-500/10 hover:text-rose-500'}`}>
              {data?.ingestion?.is_paused ? "Resume" : "Pause"}
            </button>
          </StatCard>
          <StatCard title="Meta Sync" value={syncing ? (paused ? "Paused" : data?.meta?.mode === 'matchups' ? "Deep" : "Fast") : "Idle"}
            label={data?.meta?.updated_at ? new Date(data.meta.updated_at * 1000).toLocaleTimeString() : "—"}
            color={syncing ? (paused ? "#f87171" : "#f59e0b") : "#10b981"} />
          <StatCard title="Maintenance" value="" label="Cleanup" color="#64748b">
            <button onClick={handleCleanup} disabled={cleaning}
              className="mt-3 w-full bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded py-1.5 hover:bg-slate-200 dark:hover:bg-white/10 transition-all text-[9px] font-bold uppercase tracking-wider text-slate-400 dark:text-white/30 hover:text-slate-600 dark:hover:text-white/60">
              {cleaning ? "Running..." : "Prune LP Data"}
            </button>
          </StatCard>
        </div>

        {/* Control Panel — admin-only sync controls */}
        {!selectedChamp && isAdmin && (
          <div className="mb-6 bg-white dark:bg-white/[0.02] border border-slate-200 dark:border-white/[0.06] rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-blue-500">Control Panel</h3>
                <p className="text-[10px] text-slate-400 dark:text-white/25 mt-0.5">Scrape Lolalytics data for selected patches</p>
              </div>
              <div className="flex gap-2">
                {syncing && (
                  <button onClick={handleTogglePause}
                    className="px-4 py-2 rounded text-[10px] font-bold uppercase tracking-wider border border-amber-500/20 bg-amber-500/5 text-amber-500 hover:bg-amber-500/10 transition-all">
                    {paused ? "Resume" : "Pause"}
                  </button>
                )}
                {!syncing ? (<>
                  <button onClick={() => handleSyncMeta("tierlist")} className="px-4 py-2 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-500/10 text-blue-500 border border-blue-500/20 hover:bg-blue-500/20 transition-all">Tierlist Only</button>
                  <button onClick={() => handleSyncMeta("matchups")} className="px-4 py-2 rounded text-[10px] font-bold uppercase tracking-wider bg-violet-500/10 text-violet-500 border border-violet-500/20 hover:bg-violet-500/20 transition-all">Matchups Only</button>
                  <button onClick={() => handleSyncMeta("full")} className="px-5 py-2 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-600 text-white hover:bg-blue-700 transition-all shadow-sm">Deep Sync</button>
                </>) : (
                  <button onClick={handleCancelSync} className="px-5 py-2 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-500/10 text-rose-500 border border-rose-500/20 hover:bg-rose-500/20 transition-all">Stop</button>
                )}
              </div>
            </div>
            <div className="pt-3 border-t border-slate-100 dark:border-white/[0.04]">
              <PatchSelector />
            </div>
          </div>
        )}

        {error && <div className="mb-4 px-4 py-2.5 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 rounded text-rose-600 dark:text-rose-400 text-xs font-medium">{error}</div>}

        {/* Main Explorer Card */}
        <div className="bg-white dark:bg-white/[0.02] border border-slate-200 dark:border-white/[0.06] rounded-lg overflow-hidden shadow-sm">
          <div className="p-6 border-b border-slate-100 dark:border-white/[0.04]">
            <div className="flex flex-col gap-5">
              {/* Header row */}
              <div className="flex items-center gap-4">
                {selectedChamp && (
                  <button onClick={() => setSelectedChamp(null)} className="px-3 py-1.5 bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded text-[10px] font-bold uppercase tracking-wider hover:bg-slate-200 dark:hover:bg-white/10 transition-all flex items-center gap-1.5 text-slate-500 dark:text-white/50">
                    <span className="text-blue-500">←</span> Back
                  </button>
                )}
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-black uppercase tracking-tight text-slate-900 dark:text-white">{selectedChamp ? selectedChampName : "Meta Explorer"}</h2>
                    <button onClick={isAdmin ? handleLogout : handleLogin}
                      className={`text-[9px] font-bold uppercase tracking-wider px-2.5 py-1 rounded border transition-all ${isAdmin ? "border-emerald-500/30 text-emerald-500 bg-emerald-500/5 hover:bg-rose-500/10 hover:border-rose-500/30 hover:text-rose-500" : "border-slate-300 dark:border-white/20 text-slate-400 dark:text-white/40 hover:border-blue-500/40 hover:text-blue-500"}`}>
                      {isAdmin ? "Admin ✓" : "Login"}
                    </button>
                  </div>
                  <p className="text-slate-400 dark:text-white/20 text-[10px] font-medium uppercase tracking-wider mt-0.5">{selectedChamp ? "Lane Matchups" : "Performance across tiers"}</p>
                </div>
                <div className="flex items-center gap-3">
                  <PatchSelector compact />
                  <div className="relative">
                    <input type="text" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)}
                      className="bg-slate-50 dark:bg-black/30 border border-slate-200 dark:border-white/10 rounded px-4 py-2 text-sm text-slate-800 dark:text-white placeholder:text-slate-300 dark:placeholder:text-white/15 focus:outline-none focus:border-blue-500/50 w-48 transition-all" />
                    {search && <button onClick={() => setSearch("")} className="absolute right-3 top-2.5 text-slate-300 dark:text-white/20 hover:text-slate-500 dark:hover:text-white/60 text-sm">×</button>}
                  </div>
                </div>
              </div>

              {/* Role filter */}
              <div className="flex items-center gap-5">
                <div className="flex gap-1">
                  {ROLES.map(({ key, label, icon }) => (
                    <button key={key} onClick={() => setSelectedRole(key)}
                      className={`group flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all duration-150 border ${
                        selectedRole === key
                          ? "bg-blue-600 text-white border-blue-500 shadow-sm shadow-blue-600/20"
                          : "bg-transparent border-transparent text-slate-400 dark:text-white/30 hover:text-slate-600 dark:hover:text-white/60 hover:bg-slate-100 dark:hover:bg-white/5"
                      }`}>
                      <RoleIcon icon={icon} size={14} active={selectedRole === key} />
                      {label}
                    </button>
                  ))}
                </div>
                <div className="h-5 w-px bg-slate-200 dark:bg-white/10" />
                {/* Show All toggle */}
                <button onClick={() => setShowAll(!showAll)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all border ${
                    showAll
                      ? "bg-violet-500/10 text-violet-500 border-violet-500/30"
                      : "bg-transparent border-transparent text-slate-400 dark:text-white/25 hover:text-slate-600 dark:hover:text-white/50"
                  }`}>
                  <span className={`inline-block w-3 h-3 rounded-sm border-2 transition-all ${showAll ? 'bg-violet-500 border-violet-500' : 'border-slate-300 dark:border-white/20'}`} />
                  Show All
                </button>
              </div>

              {/* Rank selector */}
              <div className="flex items-center gap-1 pt-3 border-t border-slate-100 dark:border-white/[0.04]">
                {data?.meta?.ranks?.map(rank => (
                  <button key={rank} onClick={() => setSelectedRank(rank)}
                    className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all duration-150 ${
                      selectedRank === rank
                        ? "bg-slate-800 dark:bg-white/15 text-white dark:text-white shadow-sm"
                        : "text-slate-400 dark:text-white/20 hover:text-slate-600 dark:hover:text-white/50 hover:bg-slate-100 dark:hover:bg-white/5"
                    }`}>
                    {rank}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            {selectedChamp ? (
              <MatchupTable matchupData={matchupData} selectedChampName={selectedChampName} requestSort={requestSort} sortConfig={sortConfig} />
            ) : (
              <TierListTable processedChamps={processedChamps} sortConfig={sortConfig} requestSort={requestSort} onChampClick={setSelectedChamp} champNames={data?.champ_names} />
            )}
            {processedChamps.length === 0 && !selectedChamp && (
              <div className="p-12 text-center text-slate-300 dark:text-white/15 text-sm font-medium">
                No champion data available. Run a sync to populate.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
