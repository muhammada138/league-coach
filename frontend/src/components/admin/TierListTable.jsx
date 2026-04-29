const LANE_ICON_MAP = {
  top: 'top', jungle: 'jungle', middle: 'middle', bottom: 'bottom',
  support: 'utility', mid: 'middle', bot: 'bottom', sup: 'utility', utility: 'utility',
};

const LANE_SHORT = {
  top: 'TOP', jungle: 'JNG', middle: 'MID', bottom: 'BOT', support: 'SUP',
  mid: 'MID', bot: 'BOT', sup: 'SUP', all: 'ALL', unknown: '—',
};

function LaneCell({ lane }) {
  const mapped = LANE_ICON_MAP[lane?.toLowerCase()];
  // If no specific lane or "all", show a subtle text badge
  if (!mapped || lane === 'all' || lane === 'unknown' || !lane) {
    return <span className="text-[9px] font-bold text-slate-300 dark:text-white/15 tracking-wider">{LANE_SHORT[lane] || '—'}</span>;
  }
  return (
    <img
      src={`https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/svg/position-${mapped}.svg`}
      alt={lane} width={16} height={16}
      className="opacity-60 group-hover:opacity-100 transition-opacity flex-shrink-0"
      style={{ width: 16, height: 16, objectFit: 'contain' }}
      onError={e => { e.target.style.display = 'none'; }}
    />
  );
}

function fmt(n) { return n?.toLocaleString() ?? "0"; }

const TIER_STYLES = {
  'S+': 'bg-gradient-to-r from-amber-500/25 to-orange-500/20 text-amber-400 border-amber-500/40',
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
  const Arrow = ({ col }) => sortConfig.key !== col ? null : <span className="ml-1 text-blue-400">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>;

  return (
    <table className="w-full text-left border-collapse">
      <thead>
        <tr className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-white/30 border-b border-slate-200 dark:border-white/[0.06] bg-slate-50/50 dark:bg-white/[0.015]">
          <th className="pl-5 pr-2 py-3.5 w-[60px] cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('rank_num')}>Rank<Arrow col="rank_num" /></th>
          <th className="px-2 py-3.5 w-[44px] text-center">Role</th>
          <th className="px-4 py-3.5 cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('name')}>Champion<Arrow col="name" /></th>
          <th className="px-4 py-3.5 w-[56px] text-center cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('tier_val')}>Tier<Arrow col="tier_val" /></th>
          <th className="px-4 py-3.5 w-[100px] cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('wr')}>Win Rate<Arrow col="wr" /></th>
          <th className="px-4 py-3.5 w-[90px] cursor-pointer hover:text-slate-700 dark:hover:text-white/70 transition-colors" onClick={() => requestSort('games')}>Matches<Arrow col="games" /></th>
          <th className="px-4 py-3.5 pr-5">Counter Picks</th>
        </tr>
      </thead>
      <tbody>
        {processedChamps.map((c, i) => {
          const counters = c.matchups && Object.keys(c.matchups).length > 0
            ? Object.entries(c.matchups)
                .map(([cid, raw]) => ({ cid, wr: typeof raw === 'object' ? raw.wr : raw, name: champNames?.[cid] || '' }))
                .sort((a, b) => a.wr - b.wr).slice(0, 5)
            : null;
          const tierStyle = TIER_STYLES[c.tier] || 'bg-slate-100 dark:bg-white/5 text-slate-400 dark:text-white/30 border-slate-200 dark:border-white/10';
          const displayLane = c.display_lane || c.lane || 'all';

          return (
            <tr key={i} className="group border-b border-slate-100 dark:border-white/[0.025] hover:bg-blue-50/40 dark:hover:bg-[#141c33]/60 transition-all duration-150">
              <td className="pl-5 pr-2 py-2.5 tabular-nums text-slate-300 dark:text-white/15 font-black text-xs">{c.rank_num === 999 ? '—' : c.rank_num}</td>
              <td className="px-2 py-2.5 text-center"><LaneCell lane={displayLane} /></td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-3">
                  <img
                    src={`https://cdn.communitydragon.org/latest/champion/${c.name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                    className="w-8 h-8 rounded border border-slate-200 dark:border-white/10 group-hover:border-blue-400/40 transition-all"
                    alt="" onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                  />
                  <span className="text-[13px] font-semibold capitalize text-slate-800 dark:text-white/90 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{c.name}</span>
                </div>
              </td>
              <td className="px-4 py-2.5 text-center">
                <span className={`inline-flex items-center justify-center w-8 py-0.5 rounded text-[10px] font-black border ${tierStyle}`}>{c.tier || 'N/A'}</span>
              </td>
              <td className="px-4 py-2.5 tabular-nums">
                <span className={`text-sm font-black ${c.wr >= 52 ? 'text-emerald-500' : c.wr <= 48 ? 'text-rose-500' : 'text-slate-600 dark:text-white/80'}`}>{c.wr.toFixed(2)}%</span>
              </td>
              <td className="px-4 py-2.5 tabular-nums text-xs text-slate-400 dark:text-white/25 font-medium">{fmt(c.games)}</td>
              <td className="px-4 py-2.5 pr-5">
                {counters ? (
                  <div className="flex items-center gap-1">
                    {counters.map(({ cid, wr, name }) => (
                      <div key={cid} className="relative group/tip">
                        <img
                          src={`https://cdn.communitydragon.org/latest/champion/${name.toLowerCase().replace(/[^a-z]/g, '')}/square`}
                          className="w-6 h-6 rounded border border-slate-200 dark:border-white/10 hover:border-rose-400/60 transition-all hover:scale-110"
                          alt={name} onError={e => e.target.src = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/-1.png'}
                        />
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-0.5 bg-slate-900 text-white text-[9px] font-bold rounded shadow-xl whitespace-nowrap opacity-0 group-hover/tip:opacity-100 pointer-events-none z-20 transition-opacity">
                          {name} · {wr.toFixed(1)}%
                        </div>
                      </div>
                    ))}
                    <button onClick={() => onChampClick(c.id)}
                      className="ml-1 w-6 h-6 rounded border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-400 dark:text-white/30 hover:text-blue-500 hover:border-blue-400/50 transition-all">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                    </button>
                  </div>
                ) : (
                  <button onClick={() => onChampClick(c.id)} className="text-[10px] font-bold uppercase tracking-wider text-blue-400/40 hover:text-blue-400 transition-all">View →</button>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
