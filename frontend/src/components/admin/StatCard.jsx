export default function StatCard({ title, value, label, color, children }) {
  return (
    <div className="bg-slate-50 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.07] rounded-lg p-5 shadow-sm dark:shadow-xl flex flex-col justify-between hover:border-slate-300 dark:hover:border-white/[0.12] transition-all duration-200">
      <div>
        <h2 className="text-[10px] font-black uppercase tracking-widest mb-3" style={{ color }}>{title}</h2>
        <div className="text-2xl font-black mb-1 tracking-tight tabular-nums text-slate-900 dark:text-white">{value}</div>
        <p className="text-slate-400 dark:text-white/20 text-[10px] font-bold uppercase tracking-widest">{label}</p>
      </div>
      {children}
    </div>
  );
}
