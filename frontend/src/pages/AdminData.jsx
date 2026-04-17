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
  const [search, setSearch] = useState("");

  const fetchData = async () => {
    try {
      const summary = await getAdminDataSummary();
      setData(summary);
      setError("");
      
      // Auto-select first rank if emerald isn't there
      if (summary.meta.ranks.length > 0 && !summary.meta.ranks.includes("emerald")) {
        setSelectedRank(summary.meta.ranks[0]);
      }
    } catch {
      setError("Could not reach backend.");
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSyncMeta = async () => {
    setSyncing(true);
    try {
      await syncMeta();
      setTimeout(fetchData, 3000);
    } catch {
      setError("Sync trigger failed.");
    } finally {
      setSyncing(false);
    }
  };

  const rankData = data?.meta?.details?.[selectedRank] || { champions: {}, tier_avg: 50 };
  const champions = Object.values(rankData.champions);

  const filteredChamps = useMemo(() => {
    return champions
      .filter(c => c.name.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => b.wr - a.wr);
  }, [champions, search]);

  if (!data && !error) return (
    <div className="min-h-screen flex items-center justify-center bg-[#05080f]">
      <span className="w-8 h-8 border-4 border-[#c89b3c]/30 border-t-[#c89b3c] rounded-full animate-spin" />
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
            label={`${data?.meta?.ranks?.length} Tiers Scraped`} 
            color="#3b82f6" 
          />
          <StatCard 
            title="Last Sync" 
            value={data?.meta?.updated_at ? new Date(data.meta.updated_at * 1000).toLocaleTimeString() : "Never"} 
            label={data?.meta?.updated_at ? new Date(data.meta.updated_at * 1000).toLocaleDateString() : "No Data"} 
            color="#10b981" 
          />
        </div>

        {/* Data Explorer */}
        <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl overflow-hidden backdrop-blur-md">
          
          {/* Toolbar */}
          <div className="p-8 border-b border-white/[0.05] bg-white/[0.01]">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
              <div>
                <h2 className="text-xl font-black text-white mb-1 uppercase italic tracking-tight">Lolalytics Meta Explorer</h2>
                <p className="text-white/30 text-xs font-bold uppercase tracking-widest">Verifying rank-specific winrates & deltas</p>
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
                <button
                  onClick={handleSyncMeta}
                  disabled={syncing}
                  className="px-6 py-2 rounded-xl bg-[#c89b3c] hover:bg-[#a67c2e] disabled:opacity-50 text-black text-xs font-black uppercase tracking-widest transition-all active:scale-95 flex items-center gap-2"
                >
                  {syncing ? <span className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin" /> : "Refresh Meta"}
                </button>
              </div>
            </div>

            {/* Rank Selector */}
            <div className="flex flex-wrap gap-2 mt-8">
              {data?.meta?.ranks.map(rank => (
                <button
                  key={rank}
                  onClick={() => setSelectedRank(rank)}
                  className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-tighter transition-all border ${
                    selectedRank === rank 
                      ? "bg-white/10 border-white/20 text-white" 
                      : "bg-transparent border-transparent text-white/30 hover:text-white/60"
                  }`}
                >
                  {rank}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-[10px] font-black uppercase tracking-widest text-white/20 border-b border-white/[0.05]">
                  <th className="px-8 py-4">Champion</th>
                  <th className="px-8 py-4">Win Rate</th>
                  <th className="px-8 py-4 text-center">Delta</th>
                  <th className="px-8 py-4">Tier Context</th>
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
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredChamps.length === 0 && (
              <div className="py-20 text-center text-white/20 text-sm font-bold uppercase tracking-widest">
                No data for this rank
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
      <div className="text-3xl font-black text-white mb-1 tracking-tighter">{value}</div>
      <p className="text-white/20 text-[10px] font-bold uppercase tracking-wide">{label}</p>
    </div>
  );
}
