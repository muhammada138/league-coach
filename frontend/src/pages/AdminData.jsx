import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { getAdminDataSummary, syncMeta, cancelSync, toggleSyncPause, cleanupData } from "../api/riot";

function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

const TIER_ORDER = {
  "S+": 0, "S": 1, "S-": 2, "A+": 3, "A": 4, "A-": 5, "B+": 6, "B": 7, "B-": 8, "C+": 9, "C": 10, "C-": 11, "D+": 12, "D": 13, "D-": 14, "N/A": 15
};

export default function AdminData() {
  const [data, setData] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [paused, setPaused] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedRank, setSelectedRank] = useState(searchParams.get("rank") || "emerald");
  const [selectedRole, setSelectedRole] = useState(searchParams.get("role") || "all");
  const [search, setSearch] = useState("");
  const [selectedChamp, setSelectedChamp] = useState(searchParams.get("champ") || null);

  // Keep URL in sync with filter state
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
      
      if (summary?.meta?.ranks?.length > 0) {
        if (!summary.meta.ranks.includes(selectedRank)) {
          setSelectedRank(summary.meta.ranks.includes("emerald") ? "emerald" : summary.meta.ranks[0]);
        }
      }
    } catch (err) {
      console.error(err);
      setError("Backend unreachable. Checking connection...");
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); 
    return () => clearInterval(interval);
  }, []);

  const handleSyncMeta = async (mode = "full") => {
    if (syncing) return;
    setSyncing(true);
    setError("");
    try {
      await syncMeta(mode);
    } catch (err) {
      setError("Sync failed: " + (err.response?.data?.detail || err.message));
      setSyncing(false);
    }
  };

  const handleCancelSync = async () => {
    try {
      const res = await cancelSync();
      if (!res.ok) throw new Error(res.message);
    } catch (err) {
      setError("Cancel failed: " + err.message);
    }
  };

  const handleTogglePause = async () => {
    try {
      const res = await toggleSyncPause();
      setPaused(res.paused);
    } catch {
      setError("Pause failed.");
    }
  };

  const handleCleanup = async () => {
    if (!confirm("Run standard maintenance? (Prunes LP history entries older than 30 days. Training matches are NEVER deleted.)")) return;
    setCleaning(true);
    try {
      const res = await cleanupData();
      alert(`Maintenance complete. Pruned ${res.counts.lp_history} old entries.`);
      fetchData();
    } catch {
      setError("Cleanup failed.");
    } finally {
      setCleaning(false);
    }
  };

  const rankData = useMemo(() => {
    return data?.meta?.details?.[selectedRank] || { champions: {}, tier_avg: 50 };
  }, [data, selectedRank]);

  const champions = useMemo(() => {
    return Object.entries(rankData.champions)
      .filter(([, info]) => {
        const lane = info.lane || "all";
        return selectedRole === "all" ? lane === "all" : lane === selectedRole;
      })
      .map(([key, info]) => ({
        id: key,
        cid: info.cid,
        ...info,
        name: info.name || data?.champ_names?.[info.cid] || "Unknown",
        tier_val: TIER_ORDER[info.tier] ?? 15,
        rank_num: info.rank_label && info.rank_label !== "N/A" ? parseInt(info.rank_label) : 999
      }));
  }, [rankData, data, selectedRole]);

  // Reset sort when switching between tierlist and matchup views
  useEffect(() => {
    if (selectedChamp) {
      setSortConfig({ key: 'wr', direction: 'desc' });
    } else {
      setSortConfig({ key: 'rank_num', direction: 'asc' });
    }
  }, [selectedChamp]);

  const requestSort = (key) => {
    let direction = 'desc';
    if (sortConfig.key === key && sortConfig.direction === 'desc') {
      direction = 'asc';
    }
    if (key === 'tier_val' || key === 'rank_num') {
      direction = (sortConfig.key === key && sortConfig.direction === 'asc') ? 'desc' : 'asc';
    }
    setSortConfig({ key, direction });
  };

  const processedChamps = useMemo(() => {
    let list = [...champions];
    
    // 3. Search Filter
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => c.name.toLowerCase().includes(s));
    }
    
    // 4. Final Sort
    return list.sort((a, b) => {
      let aVal = a[sortConfig.key] ?? 0;
      let bVal = b[sortConfig.key] ?? 0;
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [champions, search, selectedRole, sortConfig]);

  const selectedChampData = selectedChamp ? rankData.champions[selectedChamp] : null;
  const selectedChampName = selectedChampData?.name || data?.champ_names?.[selectedChampData?.cid || selectedChamp] || "Champion";

  const matchupData = useMemo(() => {
    if (!selectedChampData || !selectedChampData.matchups) return [];

    let list = Object.entries(selectedChampData.matchups).map(([opp_cid, raw]) => {
      const wr = typeof raw === "object" ? raw.wr : raw;
      const games = typeof raw === "object" ? raw.games : null;
      const opp_name = data?.champ_names?.[opp_cid] || "Unknown";
      return { id: opp_cid, name: opp_name, wr, games, delta: wr - 50.0 };
    });

    return list.sort((a, b) => {
      const key = ['wr', 'name', 'games'].includes(sortConfig.key) ? sortConfig.key : 'wr';
      let aVal = a[key] ?? 0;
      let bVal = b[key] ?? 0;
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [selectedChampData, data, sortConfig]);

  if (!data && !error) return (
    <div className="min-h-screen flex items-center justify-center bg-[#05080f]">
      <span className="w-12 h-12 border-4 border-[#c89b3c]/30 border-t-[#c89b3c] rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen pt-24 pb-20 px-6 bg-[#05080f] text-white">
      <div className="max-w-6xl mx-auto">
        
        {/* Header Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
          <StatCard title="Training Pool" value={fmt(data?.training?.match_count)} label="Matches" color="#c89b3c" />
          <StatCard title="Inventory" value={data?.meta?.champion_count} label="Champions" color="#3b82f6" />
          <StatCard 
            title="Status" 
            value={syncing ? (paused ? "Paused" : (data?.meta?.mode === 'matchups' ? "Deep Crawl" : "Fast Sync")) : "Standby"} 
            label={data?.meta?.updated_at ? new Date(data.meta.updated_at * 1000).toLocaleTimeString() : "No Data"}
            color={syncing ? (paused ? "#f87171" : "#f59e0b") : "#10b981"} 
          />
          <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl p-6 backdrop-blur-sm shadow-xl flex flex-col justify-between">
            <h2 className="text-[10px] font-black uppercase tracking-widest text-[#c89b3c]">Maintenance</h2>
            <div className="text-[9px] font-bold text-white/20 uppercase leading-relaxed mt-2">Training data and LP history are protected from deletion.</div>
            <button
              onClick={handleCleanup}
              disabled={cleaning}
              className="mt-3 w-full bg-white/5 border border-white/10 rounded-xl py-2 hover:bg-white/10 transition-all text-[9px] font-black uppercase tracking-widest text-white/40 hover:text-white"
            >
              {cleaning ? "Running..." : "Prune Old LP Data"}
            </button>
          </div>
        </div>

        {/* Sync Controls */}
        {!selectedChamp && (
          <div className="mb-8 flex items-center justify-between bg-white/[0.03] border border-white/[0.07] p-6 rounded-3xl">
            <div>
              <h3 className="text-sm font-black uppercase tracking-widest text-[#c89b3c]">Control Panel</h3>
              <p className="text-[10px] text-white/30 uppercase font-bold">Update Tierlist (Fast) or Matchups (Deep)</p>
            </div>
            <div className="flex gap-3">
              {syncing && (
                <button
                  onClick={handleTogglePause}
                  className="px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest border border-amber-500/20 bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 transition-all"
                >
                  {paused ? "Resume Sync" : "Pause Sync"}
                </button>
              )}
              {!syncing ? (
                <>
                  <button
                    onClick={() => handleSyncMeta("tierlist")}
                    className="px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all bg-blue-600/20 text-blue-400 border border-blue-600/20 hover:bg-blue-600/30"
                  >
                    Update Tierlist
                  </button>
                  <button
                    onClick={() => handleSyncMeta("full")}
                    className="px-8 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all bg-[#c89b3c] text-black hover:bg-[#a67c2e]"
                  >
                    Start Deep Sync
                  </button>
                </>
              ) : (
                <button
                  onClick={handleCancelSync}
                  className="px-8 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all bg-rose-500/20 text-rose-500 border border-rose-500/20 hover:bg-rose-500/30"
                >
                  Stop {data?.meta?.mode === 'tierlist' ? 'Tierlist Sync' : 'Deep Crawl'}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Explorer */}
        <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl overflow-hidden shadow-2xl backdrop-blur-sm">
          <div className="p-8 border-b border-white/[0.05]">
            <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-4">
                <div className="flex gap-4 items-center">
                  {selectedChamp && (
                    <button 
                      onClick={() => setSelectedChamp(null)}
                      className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2"
                    >
                      <span className="text-[#c89b3c]">←</span> Back to Tierlist
                    </button>
                  )}
                  <div>
                    <h2 className="text-2xl font-black uppercase italic tracking-tighter">
                      {selectedChamp ? selectedChampName : "Meta Explorer"}
                    </h2>
                    <p className="text-white/20 text-xs font-bold uppercase tracking-widest mt-1">
                      {selectedChamp ? "Specific Lane Matchups" : "Global performance across tiers"}
                    </p>
                  </div>
                </div>
                <div className="relative">
                  <input 
                    type="text"
                    placeholder="Search champion..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="bg-black/40 border border-white/10 rounded-xl px-5 py-2.5 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-[#c89b3c]/50 w-72 transition-all shadow-inner"
                  />
                  {search && <button onClick={() => setSearch("")} className="absolute right-4 top-3 text-white/20 hover:text-white">×</button>}
                </div>
              </div>

              <div className="flex flex-col gap-6">
                <div className="flex items-center gap-6">
                  <span className="text-[9px] font-black uppercase tracking-[0.2em] text-[#c89b3c] w-12 text-right">Role</span>
                  <div className="flex flex-wrap gap-2">
                    {["all", "top", "jungle", "middle", "bottom", "support"].map(role => (
                      <button
                        key={role}
                        onClick={() => setSelectedRole(role)}
                        className={`px-5 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border ${
                          selectedRole === role ? "bg-blue-600 text-white border-blue-500 shadow-lg shadow-blue-600/20" : "bg-white/5 border-white/5 text-white/30 hover:text-white/60"
                        }`}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-6 border-t border-white/[0.03] pt-6">
                  <span className="text-[9px] font-black uppercase tracking-[0.2em] text-white/20 w-12 text-right">Rank</span>
                  <div className="flex flex-wrap gap-1.5">
                    {data?.meta?.ranks.map(rank => (
                      <button
                        key={rank}
                        onClick={() => setSelectedRank(rank)}
                        className={`px-4 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all border ${
                          selectedRank === rank ? "bg-white/10 border-white/20 text-white" : "bg-transparent border-transparent text-white/20 hover:text-white/40"
                        }`}
                      >
                        {rank}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            {selectedChamp ? (
              /* ── MATCHUP VIEW ── */
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[10px] font-black uppercase tracking-widest text-white/20 border-b border-white/[0.05] bg-white/[0.01]">
                    <th className="px-6 py-5 w-12">#</th>
                    <th className="px-4 py-5">Matchup</th>
                    <th className="px-6 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('wr')}>
                      {selectedChampName}'s WR vs {sortConfig.key === 'wr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-6 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('delta')}>
                      Delta {sortConfig.key === 'delta' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-6 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('games')}>
                      Games {sortConfig.key === 'games' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.02]">
                  {matchupData.map((c, i) => (
                    <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                      <td className="px-6 py-4 tabular-nums text-white/20 font-black text-xs">#{i + 1}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <img
                            src={`https://cdn.communitydragon.org/latest/champion/${selectedChampName.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                            className="w-9 h-9 rounded-lg border border-white/10"
                            alt=""
                            onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                          />
                          <span className="text-white/20 text-[10px] font-black">VS</span>
                          <img
                            src={`https://cdn.communitydragon.org/latest/champion/${c.name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                            className="w-9 h-9 rounded-lg border border-white/10"
                            alt=""
                            onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                          />
                          <span className="text-sm font-bold capitalize ml-1 group-hover:text-[#c89b3c] transition-colors">{c.name}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 tabular-nums">
                        <span className={`text-sm font-black ${c.wr >= 52 ? 'text-emerald-400' : c.wr <= 48 ? 'text-rose-400' : 'text-white'}`}>
                          {c.wr.toFixed(2)}%
                        </span>
                      </td>
                      <td className="px-6 py-4 tabular-nums">
                        <span className={`text-xs font-black ${c.delta >= 2 ? 'text-emerald-400' : c.delta <= -2 ? 'text-rose-400' : 'text-white/50'}`}>
                          {c.delta >= 0 ? '+' : ''}{c.delta.toFixed(2)}
                        </span>
                      </td>
                      <td className="px-6 py-4 tabular-nums text-xs text-white/20">
                        {c.games != null ? fmt(c.games) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              /* ── MAIN TIERLIST VIEW ── */
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[10px] font-black uppercase tracking-widest text-white/20 border-b border-white/[0.05] bg-white/[0.01]">
                    <th className="px-8 py-5 w-16 cursor-pointer hover:text-white" onClick={() => requestSort('rank_num')}>
                      Rank {sortConfig.key === 'rank_num' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-4 py-5 w-16">Icon</th>
                    <th className="px-4 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('name')}>
                      Name {sortConfig.key === 'name' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-8 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('tier_val')}>
                      Tier {sortConfig.key === 'tier_val' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-8 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('lane')}>
                      Lane {sortConfig.key === 'lane' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-8 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('wr')}>
                      Win Rate {sortConfig.key === 'wr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-8 py-5 cursor-pointer hover:text-white" onClick={() => requestSort('games')}>
                      Games {sortConfig.key === 'games' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                    </th>
                    <th className="px-6 py-5">Counter Picks</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.02]">
                  {processedChamps.map((c, i) => {
                    const counters = c.matchups && Object.keys(c.matchups).length > 0
                      ? Object.entries(c.matchups)
                          .map(([cid, raw]) => ({ cid, wr: typeof raw === 'object' ? raw.wr : raw, name: data?.champ_names?.[cid] || '' }))
                          .sort((a, b) => a.wr - b.wr)
                          .slice(0, 7)
                      : null;
                    return (
                      <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                        <td className="px-8 py-4 tabular-nums text-white/20 font-black text-xs">
                          #{c.rank_num === 999 ? 'N/A' : c.rank_num}
                        </td>
                        <td className="px-4 py-4">
                          <img
                            src={`https://cdn.communitydragon.org/latest/champion/${c.name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                            className="w-8 h-8 rounded-lg border border-white/10"
                            alt=""
                            onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                          />
                        </td>
                        <td className="px-4 py-4">
                          <span className="text-sm font-bold capitalize group-hover:text-[#c89b3c] transition-colors">{c.name}</span>
                        </td>
                        <td className="px-8 py-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-black border ${
                            c.tier?.startsWith('S') ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' :
                            c.tier?.startsWith('A') ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                            c.tier?.startsWith('B') ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' :
                            'bg-white/5 border-white/10 text-white/30'
                          }`}>
                            {c.tier || 'N/A'}
                          </span>
                        </td>
                        <td className="px-8 py-4">
                          <span className="text-[10px] font-black uppercase text-white/30">{c.lane || 'unknown'}</span>
                        </td>
                        <td className="px-8 py-4 tabular-nums">
                          <span className={`text-sm font-black ${c.wr >= 52 ? 'text-emerald-400' : c.wr <= 48 ? 'text-rose-400' : 'text-white'}`}>
                            {c.wr.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-8 py-4 tabular-nums text-xs text-white/20">{fmt(c.games)}</td>
                        <td className="px-6 py-4">
                          {counters ? (
                            <div className="flex items-center gap-1">
                              {counters.map(({ cid, wr, name }) => (
                                <div key={cid} className="relative group/tip">
                                  <img
                                    src={`https://cdn.communitydragon.org/latest/champion/${name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                                    className="w-7 h-7 rounded-md border border-white/10 cursor-pointer hover:border-rose-400/50 transition-all"
                                    alt={name}
                                    onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                                  />
                                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-0.5 bg-black/90 border border-white/10 text-white text-[9px] font-black rounded whitespace-nowrap opacity-0 group-hover/tip:opacity-100 pointer-events-none z-10">
                                    {name} · {wr.toFixed(1)}%
                                  </div>
                                </div>
                              ))}
                              <button
                                onClick={() => setSelectedChamp(c.id)}
                                className="ml-1 text-[9px] font-black uppercase text-white/20 hover:text-[#c89b3c] transition-all"
                              >
                                All →
                              </button>
                            </div>
                          ) : (
                            <button onClick={() => setSelectedChamp(c.id)} className="text-[10px] font-black uppercase tracking-widest text-[#c89b3c]/30 hover:text-[#c89b3c] transition-all">
                              Matchups
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
      </div>
    </div>
    </div>
  );
}

function StatCard({ title, value, label, color }) {
  return (
    <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl p-6 backdrop-blur-sm shadow-xl">
      <h2 className="text-[10px] font-black uppercase tracking-widest mb-4" style={{ color }}>{title}</h2>
      <div className="text-3xl font-black mb-1 tracking-tighter tabular-nums">{value}</div>
      <p className="text-white/20 text-[10px] font-bold uppercase tracking-widest">{label}</p>
    </div>
  );
}
