function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function TierListTable({ processedChamps, sortConfig, requestSort, onChampClick, champNames }) {
  return (
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
                .map(([cid, raw]) => ({ 
                  cid, 
                  wr: typeof raw === 'object' ? raw.wr : raw, 
                  name: champNames?.[cid] || '' 
                }))
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
                      onClick={() => onChampClick(c.id)}
                      className="ml-1 text-[9px] font-black uppercase text-white/20 hover:text-[#c89b3c] transition-all"
                    >
                      All →
                    </button>
                  </div>
                ) : (
                  <button onClick={() => onChampClick(c.id)} className="text-[10px] font-black uppercase tracking-widest text-[#c89b3c]/30 hover:text-[#c89b3c] transition-all">
                    Matchups
                  </button>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
