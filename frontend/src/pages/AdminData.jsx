import { useEffect, useState, useMemo } from "react";
import { getAdminDataSummary, syncMeta } from "../api/riot";

function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function AdminData() {
  const [data, setData] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [selectedRank, setSelectedRank] = useState("emerald");
  const [selectedRole, setSelectedRole] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedChamp, setSelectedChamp] = useState(null);

  const fetchData = async () => {
    try {
      const summary = await getAdminDataSummary();
      setData(summary);
      setError("");
      
      // Initialize selectedRank if not set or emerald missing
      if (summary?.meta?.ranks?.length > 0) {
        if (!summary.meta.ranks.includes(selectedRank)) {
          setSelectedRank(summary.meta.ranks.includes("emerald") ? "emerald" : summary.meta.ranks[0]);
        }
      }
    } catch (err) {
      console.error(err);
      setError("Could not reach backend. Ensure it is running and accessible.");
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Poll every 10s during sync
    return () => clearInterval(interval);
  }, []);

  const handleSyncMeta = async () => {
    if (syncing) return;
    setSyncing(true);
    setError("");
    try {
      await syncMeta();
      // Sync started in background, polling will catch updates
    } catch (err) {
      setError("Failed to start sync: " + (err.response?.data?.detail || err.message));
      setSyncing(false);
    }
  };

  const rankData = useMemo(() => {
    return data?.meta?.details?.[selectedRank] || { champions: {}, tier_avg: 50 };
  }, [data, selectedRank]);

  const champions = useMemo(() => {
    return Object.entries(rankData.champions).map(([cid, info]) => ({
      id: cid,
      ...info
    }));
  }, [rankData]);

  const filteredChamps = useMemo(() => {
    let list = [...champions];
    if (selectedRole !== "all") {
      list = list.filter(c => c.lane?.toLowerCase() === selectedRole);
    }
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c => c.name.toLowerCase().includes(s));
    }
    return list.sort((a, b) => b.wr - a.wr);
  }, [champions, search, selectedRole]);

  const selectedChampData = selectedChamp ? rankData.champions[selectedChamp] : null;
  
  const matchupData = useMemo(() => {
    if (!selectedChampData || !selectedChampData.matchups) return [];
    
    return Object.entries(selectedChampData.matchups).map(([opp_cid, wr]) => {
      const opp_champ = rankData.champions[opp_cid];
      const opp_name = opp_champ ? opp_champ.name : "Unknown";
      const delta = wr - 50.0;
      return { id: opp_cid, name: opp_name, wr, delta };
    }).sort((a, b) => b.wr - a.wr);
  }, [selectedChampData, rankData]);

  if (!data && !error) return (
    <div className="min-h-screen flex items-center justify-center bg-[#05080f]">
      <div className="flex flex-col items-center gap-4">
        <span className="w-12 h-12 border-4 border-[#c89b3c]/30 border-t-[#c89b3c] rounded-full animate-spin" />
        <p className="text-white/20 text-xs font-black uppercase tracking-widest">Loading Inventory...</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen pt-24 pb-20 px-6 bg-[#05080f]">
      <div className="max-w-6xl mx-auto">
        
        {/* Top Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
          <StatCard title="Training Pool" value={fmt(data?.training?.match_count)} label="Unique Matches" color="#c89b3c" />
          <StatCard 
            title="Meta Coverage" 
            value={data?.meta?.champion_count} 
            label={`${data?.meta?.ranks?.length || 0} Tiers Scraped`} 
            color="#3b82f6" 
          />
          <StatCard 
            title="Update Status" 
            value={data?.meta?.updated_at ? new Date(data.meta.updated_at * 1000).toLocaleTimeString() : "No Data"} 
            label={syncing ? "Syncing Matchups..." : (data?.meta?.updated_at ? new Date(data.meta.updated_at * 1000).toLocaleDateString() : "Standby")} 
            color={syncing ? "#f59e0b" : "#10b981"} 
          />
        </div>

        {error && (
          <div className="mb-8 p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-bold">
            ⚠️ {error}
          </div>
        )}

        {/* Data Explorer */}
        <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl overflow-hidden backdrop-blur-md">
          
          {/* Toolbar */}
          <div className="p-8 border-b border-white/[0.05] bg-white/[0.01]">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
              <div>
                <h2 className="text-xl font-black text-white mb-1 uppercase italic tracking-tight flex items-center gap-3">
                  {selectedChamp ? (
                    <>
                      <button onClick={() => setSelectedChamp(null)} className="hover:text-[#c89b3c] transition-colors">Explorer</button>
                      <span className="text-white/20">/</span>
                      <span>{selectedChampData?.name} Matchups</span>
                    </>
                  ) : (
                    "Lolalytics Meta Explorer"
                  )}
                </h2>
                <p className="text-white/30 text-xs font-bold uppercase tracking-widest">
                  {selectedChamp ? `Specific matchup winrates for ${selectedChampData?.name}` : "Verifying rank-specific winrates & deltas"}
                </p>
              </div>
              
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative">
                  <input 
                    type="text"
                    placeholder="Search champion..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-[#c89b3c]/50 w-64 transition-all"
                  />
                  {search && (
                    <button onClick={() => setSearch("")} className="absolute right-3 top-2.5 text-white/20 hover:text-white">×</button>
                  )}
                </div>
                {selectedChamp ? (
                  <button
                    onClick={() => setSelectedChamp(null)}
                    className="px-6 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-black uppercase tracking-widest transition-all active:scale-95"
                  >
                    Back to Tierlist
                  </button>
                ) : (
                  <button
                    onClick={handleSyncMeta}
                    disabled={syncing}
                    className={`px-6 py-2 rounded-xl text-xs font-black uppercase tracking-widest transition-all active:scale-95 flex items-center gap-2 ${
                      syncing ? 'bg-amber-500/20 text-amber-500' : 'bg-[#c89b3c] text-black hover:bg-[#a67c2e]'
                    }`}
                  >
                    {syncing ? (
                      <>
                        <span className="w-3 h-3 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
                        Syncing...
                      </>
                    ) : (
                      "Deep Sync All"
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Rank Selector */}
            <div className="flex flex-col md:flex-row gap-4 mt-8">
              <div className="flex flex-wrap gap-2">
                {data?.meta?.ranks.map(rank => (
                  <button
                    key={rank}
                    onClick={() => { setSelectedRank(rank); setSelectedChamp(null); }}
                    className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-tighter transition-all border ${
                      selectedRank === rank 
                        ? "bg-white/10 border-white/20 text-white shadow-lg shadow-white/5" 
                        : "bg-transparent border-transparent text-white/30 hover:text-white/60"
                    }`}
                  >
                    {rank}
                  </button>
                ))}
              </div>
              <div className="w-px h-6 bg-white/5 hidden md:block" />
              <div className="flex flex-wrap gap-2">
                {["all", "top", "jungle", "middle", "bottom", "support"].map(role => (
                  <button
                    key={role}
                    onClick={() => setSelectedRole(role)}
                    className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-tighter transition-all border ${
                      selectedRole === role 
                        ? "bg-blue-500/20 border-blue-500/30 text-blue-400" 
                        : "bg-transparent border-transparent text-white/30 hover:text-white/60"
                    }`}
                  >
                    {role}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto">
            {selectedChamp ? (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[10px] font-black uppercase tracking-widest text-white/20 border-b border-white/[0.05]">
                    <th className="px-8 py-4">Opponent</th>
                    <th className="px-8 py-4">Matchup Winrate</th>
                    <th className="px-8 py-4 text-center">Advantage (Delta)</th>
                    <th className="px-8 py-4 text-right">Raw Stats</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.02]">
                  {matchupData.map((m, i) => (
                    <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                      <td className="px-8 py-4 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 overflow-hidden">
                          <img 
                            src={`https://cdn.communitydragon.org/latest/champion/${m.name.toLowerCase().replace(/[^a-z]/g, '')}/square`} 
                            alt=""
                            onError={(e) => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                          />
                        </div>
                        <span className="text-sm font-bold text-white group-hover:text-[#c89b3c] transition-colors capitalize">{m.name}</span>
                      </td>
                      <td className="px-8 py-4 tabular-nums">
                        <span className={`text-sm font-black ${m.wr >= 52 ? 'text-emerald-400' : m.wr <= 48 ? 'text-rose-400' : 'text-white'}`}>
                          {m.wr.toFixed(2)}%
                        </span>
                      </td>
                      <td className="px-8 py-4 text-center tabular-nums">
                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${m.delta > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                          {m.delta > 0 ? '+' : ''}{m.delta.toFixed(2)}%
                        </span>
                      </td>
                      <td className="px-8 py-4 text-right text-[10px] font-bold text-white/10 uppercase tracking-tighter">
                        Base 50.00
                      </td>
                    </tr>
                  ))}
                  {matchupData.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-8 py-20 text-center">
                        <p className="text-white/40 text-sm italic mb-2">No specific matchup data for this champion yet.</p>
                        <p className="text-white/10 text-[10px] uppercase font-black tracking-widest">Run "Deep Sync All" to populate all 25,000+ counter combinations.</p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[10px] font-black uppercase tracking-widest text-white/20 border-b border-white/[0.05]">
                    <th className="px-8 py-4">Champion</th>
                    <th className="px-8 py-4">Win Rate</th>
                    <th className="px-8 py-4 text-center">Delta</th>
                    <th className="px-8 py-4">Tier Context</th>
                    <th className="px-8 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.02]">
                  {filteredChamps.map((c, i) => (
                    <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                      <td className="px-8 py-4 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 overflow-hidden">
                          <img 
                            src={`https://cdn.communitydragon.org/latest/champion/${c.name.toLowerCase().replace(/[^a-z]/g, '')}/square`} 
                            alt=""
                            onError={(e) => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                          />
                        </div>
                        <span className="text-sm font-bold text-white group-hover:text-[#c89b3c] transition-colors capitalize">{c.name}</span>
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
                        <div className="flex items-center gap-2">
                          <div className="flex-grow h-1 bg-white/5 rounded-full overflow-hidden w-24">
                            <div className="h-full bg-white/20" style={{ width: `${(c.wr / 60) * 100}%` }} />
                          </div>
                          <span className="text-[10px] font-bold text-white/20">Avg: {rankData.tier_avg}%</span>
                        </div>
                      </td>
                      <td className="px-8 py-4 text-right">
                        <button
                          onClick={() => setSelectedChamp(c.id)}
                          className="px-4 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white text-[10px] font-black uppercase tracking-widest transition-all"
                        >
                          Matchups {Object.keys(c.matchups || {}).length > 0 ? `(${Object.keys(c.matchups).length})` : ""}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {filteredChamps.length === 0 && !selectedChamp && (
              <div className="py-24 text-center">
                <p className="text-white/10 text-sm font-black uppercase tracking-widest mb-2">No champions match "{search}"</p>
                <button onClick={() => setSearch("")} className="text-[#c89b3c] text-xs font-bold uppercase underline decoration-2 underline-offset-4">Clear Search</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, label, color }) {
  return (
    <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl p-6 backdrop-blur-sm">
      <h2 className="text-[10px] font-black uppercase tracking-widest mb-4" style={{ color }}>{title}</h2>
      <div className="text-3xl font-black text-white mb-1 tracking-tighter tabular-nums">{value}</div>
      <p className="text-white/20 text-[10px] font-bold uppercase tracking-wide">{label}</p>
    </div>
  );
}
