import { useEffect, useState, useMemo } from "react";
import { getAdminDataSummary, syncMeta, cancelSync, toggleSyncPause, cleanupData } from "../api/riot";

function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function AdminData() {
  const [data, setData] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [paused, setPaused] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState("");
  const [selectedRank, setSelectedRank] = useState("emerald");
  const [selectedRole, setSelectedRole] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedChamp, setSelectedChamp] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: 'wr', direction: 'desc' });

  const fetchData = async () => {
    try {
      const summary = await getAdminDataSummary();
      setData(summary);
      setError("");
      
      // Update sync state from backend
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
    const interval = setInterval(fetchData, 4000); 
    return () => clearInterval(interval);
  }, []);

  const handleSyncMeta = async () => {
    if (syncing) return;
    setSyncing(true);
    setError("");
    try {
      await syncMeta();
    } catch (err) {
      setError("Sync failed: " + (err.response?.data?.detail || err.message));
      setSyncing(false);
    }
  };

  const handleCancelSync = async () => {
    try {
      const res = await cancelSync();
      if (!res.ok) throw new Error(res.message);
      // Wait for poller
    } catch (err) {
      setError("Cancel failed: " + err.message);
    }
  };

  const handleTogglePause = async () => {
    try {
      const res = await toggleSyncPause();
      setPaused(res.paused);
    } catch (err) {
      setError("Pause failed.");
    }
  };

  const handleCleanup = async () => {
    if (!confirm("Are you sure? This will delete old history permanently.")) return;
    setCleaning(true);
    try {
      const res = await cleanupData();
      alert(`Deleted ${res.counts.lp_history} entries.`);
      fetchData();
    } catch (err) {
      setError("Cleanup failed.");
    } finally {
      setCleaning(false);
    }
  };

  const rankData = useMemo(() => {
    return data?.meta?.details?.[selectedRank] || { champions: {}, tier_avg: 50 };
  }, [data, selectedRank]);

  const champions = useMemo(() => {
    return Object.entries(rankData.champions).map(([cid, info]) => ({
      id: cid,
      ...info,
      name: info.name || data?.champ_names?.[cid] || "Unknown"
    }));
  }, [rankData, data]);

  const requestSort = (key) => {
    let direction = 'desc';
    if (sortConfig.key === key && sortConfig.direction === 'desc') {
      direction = 'asc';
    }
    setSortConfig({ key, direction });
  };

  const filteredChamps = useMemo(() => {
    let list = [...champions];
    if (selectedRole !== "all") {
      list = list.filter(c => c.lane?.toLowerCase() === selectedRole);
    }
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => c.name.toLowerCase().includes(s));
    }
    
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
            value={syncing ? (paused ? "Paused" : "Syncing") : "Standby"} 
            label={data?.meta?.updated_at ? new Date(data.meta.updated_at * 1000).toLocaleTimeString() : "No Data"}
            color={syncing ? (paused ? "#f87171" : "#f59e0b") : "#10b981"} 
          />
          <button
            onClick={handleCleanup}
            disabled={cleaning}
            className="h-full bg-white/[0.03] border border-white/[0.07] rounded-3xl p-6 hover:bg-white/[0.05] transition-all text-xs font-black uppercase tracking-widest text-white/40 hover:text-white"
          >
            {cleaning ? "Cleaning..." : "Purge Stale Data"}
          </button>
        </div>

        {/* Sync Controls */}
        {!selectedChamp && (
          <div className="mb-8 flex items-center justify-between bg-white/[0.03] border border-white/[0.07] p-6 rounded-3xl">
            <div>
              <h3 className="text-sm font-black uppercase tracking-widest text-[#c89b3c]">Control Panel</h3>
              <p className="text-[10px] text-white/30 uppercase font-bold">Manage background meta-data crawling</p>
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
              <button
                onClick={syncing ? handleCancelSync : handleSyncMeta}
                className={`px-8 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                  syncing ? 'bg-rose-500/20 text-rose-500 border border-rose-500/20 hover:bg-rose-500/30' : 'bg-[#c89b3c] text-black hover:bg-[#a67c2e]'
                }`}
              >
                {syncing ? "Stop Crawl" : "Start Deep Sync"}
              </button>
            </div>
          </div>
        )}

        {/* Explorer */}
        <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl overflow-hidden shadow-2xl backdrop-blur-sm">
          <div className="p-8 border-b border-white/[0.05]">
            <div className="flex flex-col gap-8">
              <div className="flex justify-between items-end">
                <div>
                  <h2 className="text-2xl font-black uppercase italic tracking-tighter">
                    {selectedChamp ? data?.champ_names?.[selectedChamp] : "Meta Explorer"}
                  </h2>
                  <p className="text-white/20 text-xs font-bold uppercase tracking-widest mt-1">
                    {selectedChamp ? "Specific Lane Matchups" : "Global performance across tiers"}
                  </p>
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

              {/* Lane Filter (Top Level) */}
              <div className="flex items-center gap-6">
                <span className="text-[9px] font-black uppercase tracking-[0.2em] text-[#c89b3c]">Role</span>
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

              {/* Rank Filter (Sub Level) */}
              <div className="flex items-center gap-6 border-t border-white/[0.03] pt-6">
                <span className="text-[9px] font-black uppercase tracking-[0.2em] text-white/20">Tier</span>
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

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-[10px] font-black uppercase tracking-widest text-white/20 border-b border-white/[0.05] bg-white/[0.01]">
                  <th className="px-8 py-5 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('name')}>
                    Champion {sortConfig.key === 'name' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-8 py-5 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('wr')}>
                    Win Rate {sortConfig.key === 'wr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-8 py-5 text-center cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('delta')}>
                    Delta {sortConfig.key === 'delta' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="px-8 py-5">Context</th>
                  <th className="px-8 py-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.02]">
                {filteredChamps.map((c, i) => (
                  <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="px-8 py-4 flex items-center gap-4">
                      <img 
                        src={`https://cdn.communitydragon.org/latest/champion/${c.name.toLowerCase().replace(/[^a-z]/g, '')}/square`} 
                        className="w-8 h-8 rounded-lg border border-white/10"
                        alt=""
                        onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                      />
                      <span className="text-sm font-bold capitalize group-hover:text-[#c89b3c] transition-colors">{c.name}</span>
                    </td>
                    <td className="px-8 py-4 tabular-nums">
                      <span className={`text-sm font-black ${c.wr >= 52 ? 'text-emerald-400' : c.wr <= 48 ? 'text-rose-400' : 'text-white'}`}>
                        {c.wr.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-8 py-4 text-center tabular-nums">
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${c.delta > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                        {c.delta > 0 ? '+' : ''}{c.delta.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-8 py-4">
                       <span className="text-[10px] font-black uppercase text-white/10 tabular-nums">Avg {rankData.tier_avg}%</span>
                    </td>
                    <td className="px-8 py-4 text-right">
                       <button onClick={() => setSelectedChamp(c.id)} className="text-[10px] font-black uppercase tracking-widest text-[#c89b3c]/40 hover:text-[#c89b3c] transition-all">Matchups</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
