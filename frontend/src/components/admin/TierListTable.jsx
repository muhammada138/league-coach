const LANE_ICON_MAP = {
  top: 'top',
  jungle: 'jungle',
  middle: 'middle',
  bottom: 'bottom',
  support: 'utility',
  mid: 'middle',
  bot: 'bottom',
  sup: 'utility',
  utility: 'utility',
};

const LANE_LABELS = {
  top: 'Top',
  jungle: 'Jng',
  middle: 'Mid',
  bottom: 'Bot',
  support: 'Sup',
};

function LaneIcon({ lane, size = 16 }) {
  const mapped = LANE_ICON_MAP[lane?.toLowerCase()] || null;
  if (!mapped || lane === 'all' || lane === 'unknown') return null;
  return (
    <img
      src={`https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/svg/position-${mapped}.svg`}
      alt={lane}
      width={size}
      height={size}
      className="inline-block opacity-60 group-hover:opacity-100 transition-opacity"
      onError={e => e.target.style.display = 'none'}
    />
  );
}

function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

const TIER_STYLES = {
  'S+': 'bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-400 border-amber-500/40 font-black',
  'S':  'bg-amber-500/15 text-amber-400 border-amber-500/30',
  'S-': 'bg-amber-500/10 text-amber-500/80 border-amber-500/20',
  'A+': 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  'A':  'bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20',
  'A-': 'bg-emerald-500/8 text-emerald-500/60 border-emerald-500/15',
  'B+': 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  'B':  'bg-blue-500/10 text-blue-400/80 border-blue-500/20',
  'B-': 'bg-blue-500/8 text-blue-500/60 border-blue-500/15',
  'C+': 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  'C':  'bg-slate-500/10 text-slate-400/80 border-slate-500/20',
  'C-': 'bg-slate-500/8 text-slate-500/60 border-slate-500/15',
  'D+': 'bg-rose-500/15 text-rose-400 border-rose-500/30',
  'D':  'bg-rose-500/10 text-rose-400/80 border-rose-500/20',
  'D-': 'bg-rose-500/8 text-rose-500/60 border-rose-500/15',
};

export default function TierListTable({ processedChamps, sortConfig, requestSort, onChampClick, champNames }) {
  const SortArrow = ({ col }) => {
    if (sortConfig.key !== col) return null;
    return <span className="ml-1 text-blue-400">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <table className="w-full text-left border-collapse">
      <thead>
        <tr className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-white/30 border-b border-slate-200 dark:border-white/[0.06] bg-slate-50/50 dark:bg-white/[0.015]">
          <th className="pl-6 pr-2 py-4 w-14 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('rank_num')}>
            Rank<SortArrow col="rank_num" />
          </th>
          <th className="px-2 py-4 w-10">Role</th>
          <th className="px-4 py-4 w-14"></th>
          <th className="px-2 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('name')}>
            Champion<SortArrow col="name" />
          </th>
          <th className="px-4 py-4 w-16 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors text-center" onClick={() => requestSort('tier_val')}>
            Tier<SortArrow col="tier_val" />
          </th>
          <th className="px-4 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('wr')}>
            Win Rate<SortArrow col="wr" />
          </th>
          <th className="px-4 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('games')}>
            Matches<SortArrow col="games" />
          </th>
          <th className="px-4 py-4 pr-6">Counter Picks</th>
        </tr>
      </thead>
      <tbody>
        {processedChamps.map((c, i) => {
          const counters = c.matchups && Object.keys(c.matchups).length > 0
            ? Object.entries(c.matchups)
                .map(([cid, raw]) => ({ 
                  cid, 
                  wr: typeof raw === 'object' ? raw.wr : raw, 
                  name: champNames?.[cid] || '' 
                }))
                .sort((a, b) => a.wr - b.wr)
                .slice(0, 5)
            : null;

          const tierStyle = TIER_STYLES[c.tier] || 'bg-slate-100 dark:bg-white/5 text-slate-400 dark:text-white/30 border-slate-200 dark:border-white/10';
          const displayLane = c.display_lane || c.lane || 'all';

          return (
            <tr 
              key={i} 
              className="group border-b border-slate-100 dark:border-white/[0.025] hover:bg-blue-50/50 dark:hover:bg-[#1a2040]/50 transition-all duration-150 cursor-default"
              style={{ animationDelay: `${i * 15}ms` }}
            >
              <td className="pl-6 pr-2 py-3 tabular-nums text-slate-300 dark:text-white/15 font-black text-xs">
                {c.rank_num === 999 ? '—' : c.rank_num}
              </td>
              <td className="px-2 py-3">
                <div className="w-5 h-5 flex items-center justify-center">
                  <LaneIcon lane={displayLane} size={18} />
                </div>
              </td>
              <td className="px-4 py-3">
                <img
                  src={`https://cdn.communitydragon.org/latest/champion/${c.name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                  className="w-8 h-8 rounded border border-slate-200 dark:border-white/10 group-hover:border-blue-400/50 dark:group-hover:border-blue-400/30 transition-all duration-150"
                  alt=""
                  onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                />
              </td>
              <td className="px-2 py-3">
                <span className="text-sm font-semibold capitalize text-slate-800 dark:text-white/90 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-150">{c.name}</span>
              </td>
              <td className="px-4 py-3 text-center">
                <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-black border ${tierStyle}`}>
                  {c.tier || 'N/A'}
                </span>
              </td>
              <td className="px-4 py-3 tabular-nums">
                <span className={`text-sm font-black ${c.wr >= 52 ? 'text-emerald-500' : c.wr <= 48 ? 'text-rose-500' : 'text-slate-600 dark:text-white/80'}`}>
                  {c.wr.toFixed(2)}%
                </span>
              </td>
              <td className="px-4 py-3 tabular-nums text-xs text-slate-400 dark:text-white/25 font-medium">{fmt(c.games)}</td>
              <td className="px-4 py-3 pr-6">
                {counters ? (
                  <div className="flex items-center gap-1">
                    {counters.map(({ cid, wr, name }) => (
                      <div key={cid} className="relative group/tip">
                        <img
                          src={`https://cdn.communitydragon.org/latest/champion/${name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                          className="w-7 h-7 rounded border border-slate-200 dark:border-white/10 hover:border-rose-400/60 dark:hover:border-rose-400/50 transition-all duration-150 hover:scale-110"
                          alt={name}
                          onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                        />
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2.5 py-1 bg-slate-900 text-white text-[9px] font-bold rounded shadow-xl whitespace-nowrap opacity-0 group-hover/tip:opacity-100 pointer-events-none z-20 transition-opacity duration-100">
                          {name} · {wr.toFixed(1)}%
                          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-slate-900" />
                        </div>
                      </div>
                    ))}
                    <button
                      onClick={() => onChampClick(c.id)}
                      className="ml-1.5 w-7 h-7 rounded border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-300 dark:text-white/20 hover:text-blue-500 dark:hover:text-blue-400 hover:border-blue-400/50 transition-all duration-150 text-xs font-bold"
                    >
                      ›
                    </button>
                  </div>
                ) : (
                  <button onClick={() => onChampClick(c.id)} className="text-[10px] font-bold uppercase tracking-wider text-blue-400/40 hover:text-blue-400 transition-all duration-150">
                    View →
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
