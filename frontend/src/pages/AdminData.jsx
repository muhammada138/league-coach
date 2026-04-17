import { useEffect, useState } from "react";
import { getAdminDataSummary, syncMeta } from "../api/riot";

function fmt(n) {
  return n?.toLocaleString() ?? "0";
}

export default function AdminData() {
  const [data, setData] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  const fetchData = async () => {
    try {
      const summary = await getAdminDataSummary();
      setData(summary);
      setError("");
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
      // Refetch after a short delay
      setTimeout(fetchData, 2000);
    } catch {
      setError("Sync trigger failed.");
    } finally {
      setSyncing(false);
    }
  };

  if (!data && !error) return (
    <div className="min-h-screen flex items-center justify-center bg-[#05080f]">
      <span className="w-8 h-8 border-4 border-[#c89b3c]/30 border-t-[#c89b3c] rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen pt-24 pb-20 px-6 bg-[#05080f]">
      
      <div className="max-w-4xl mx-auto">
        
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-3xl font-black tracking-tight text-white mb-2">
            Data Inventory
          </h1>
          <p className="text-white/40">
            A real-time overview of the datasets powering the win predictor.
          </p>
        </div>

        {error && (
          <div className="mb-8 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
          
          {/* Training Data Card */}
          <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-6 backdrop-blur-sm">
            <h2 className="text-[11px] font-black uppercase tracking-widest text-[#c89b3c] mb-4">
              Training matches
            </h2>
            <div className="text-4xl font-black text-white mb-2">
              {fmt(data?.training?.match_count)}
            </div>
            <p className="text-white/30 text-xs">
              Total unique matches in the XGBoost training set.
            </p>
          </div>

          {/* Ingestion Card */}
          <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-6 backdrop-blur-sm">
            <h2 className="text-[11px] font-black uppercase tracking-widest text-emerald-400 mb-4">
              Ingestion Status
            </h2>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-4xl font-black text-white">
                {fmt(data?.ingestion?.processed_count)}
              </span>
              <span className="text-white/20 font-bold">/ {fmt(data?.ingestion?.total_target)}</span>
            </div>
            <div className={`text-[10px] font-bold uppercase tracking-wider ${data?.ingestion?.is_paused ? 'text-amber-400' : 'text-emerald-400 animate-pulse'}`}>
               • {data?.ingestion?.is_paused ? "Paused" : "Actively Scraping"}
            </div>
          </div>

        </div>

        {/* Champion Meta Section */}
        <div className="bg-white/[0.03] border border-white/[0.07] rounded-2xl p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-[11px] font-black uppercase tracking-widest text-blue-400 mb-1">
                Lolalytics Meta
              </h2>
              <h3 className="text-xl font-bold text-white">Champion Statistics</h3>
            </div>
            <button
              onClick={handleSyncMeta}
              disabled={syncing}
              className="px-5 py-2.5 rounded-lg bg-blue-500 hover:bg-blue-600 disabled:opacity-50 
                text-white text-xs font-bold transition-all active:scale-95 flex items-center gap-2 shadow-lg shadow-blue-500/20"
            >
              {syncing ? (
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
              Sync Now
            </button>
          </div>

          {!data?.meta?.updated_at ? (
            <div className="py-12 text-center">
              <p className="text-white/20 text-sm italic">No meta data available. Click "Sync Now" to scrape Lolalytics.</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <div className="text-[9px] font-bold text-white/20 uppercase tracking-widest mb-1">Last Updated</div>
                  <div className="text-white text-xs font-medium">
                    {new Date(data.meta.updated_at * 1000).toLocaleString()}
                  </div>
                </div>
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <div className="text-[9px] font-bold text-white/20 uppercase tracking-widest mb-1">Champions</div>
                  <div className="text-white text-sm font-black">{data.meta.champion_count}</div>
                </div>
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <div className="text-[9px] font-bold text-white/20 uppercase tracking-widest mb-1">Rank Tiers</div>
                  <div className="text-white text-sm font-black">{data.meta.ranks.length}</div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {data.meta.ranks.map(rank => (
                  <span key={rank} className="px-3 py-1 rounded-md bg-white/[0.04] border border-white/[0.1] text-[10px] font-bold text-white/60 uppercase">
                    {rank}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
