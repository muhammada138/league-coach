function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function MatchupTable({ matchupData, selectedChampName, requestSort, sortConfig }) {
  return (
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
  );
}
