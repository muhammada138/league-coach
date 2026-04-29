function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function MatchupTable({ matchupData, selectedChampName, requestSort, sortConfig }) {
  const SortArrow = ({ col }) => {
    if (sortConfig.key !== col) return null;
    return <span className="ml-1 text-blue-400">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <table className="w-full text-left border-collapse">
      <thead>
        <tr className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-white/30 border-b border-slate-200 dark:border-white/[0.06] bg-slate-50/50 dark:bg-white/[0.015]">
          <th className="px-6 py-4 w-12">#</th>
          <th className="px-4 py-4">Matchup</th>
          <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('wr')}>
            {selectedChampName}'s WR vs<SortArrow col="wr" />
          </th>
          <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('delta')}>
            Delta<SortArrow col="delta" />
          </th>
          <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('games')}>
            Games<SortArrow col="games" />
          </th>
        </tr>
      </thead>
      <tbody>
        {matchupData.map((c, i) => (
          <tr key={c.id} className="group border-b border-slate-100 dark:border-white/[0.025] hover:bg-blue-50/50 dark:hover:bg-[#1a2040]/50 transition-all duration-150">
            <td className="px-6 py-3.5 tabular-nums text-slate-300 dark:text-white/15 font-black text-xs">#{i + 1}</td>
            <td className="px-4 py-3">
              <div className="flex items-center gap-2">
                <img
                  src={`https://cdn.communitydragon.org/latest/champion/${selectedChampName.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                  className="w-8 h-8 rounded border border-slate-200 dark:border-white/10"
                  alt="" loading="lazy"
                  onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                />
                <span className="text-slate-300 dark:text-white/15 text-[10px] font-black">VS</span>
                <img
                  src={`https://cdn.communitydragon.org/latest/champion/${c.name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                  className="w-8 h-8 rounded border border-slate-200 dark:border-white/10 group-hover:border-blue-400/40 transition-all"
                  alt="" loading="lazy"
                  onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                />
                <span className="text-sm font-semibold capitalize ml-1 text-slate-800 dark:text-white/90 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{c.name}</span>
              </div>
            </td>
            <td className="px-6 py-3.5 tabular-nums">
              <span className={`text-sm font-black ${c.wr >= 52 ? 'text-emerald-500' : c.wr <= 48 ? 'text-rose-500' : 'text-slate-600 dark:text-white/80'}`}>
                {c.wr.toFixed(2)}%
              </span>
            </td>
            <td className="px-6 py-3.5 tabular-nums">
              <span className={`text-xs font-bold ${c.delta >= 2 ? 'text-emerald-500' : c.delta <= -2 ? 'text-rose-500' : 'text-slate-400 dark:text-white/40'}`}>
                {c.delta >= 0 ? '+' : ''}{c.delta.toFixed(2)}
              </span>
            </td>
            <td className="px-6 py-3.5 tabular-nums text-xs text-slate-400 dark:text-white/25 font-medium">
              {c.games != null ? fmt(c.games) : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
