export default function StatCard({ title, value, label, color, children }) {
  return (
    <div className="bg-white/[0.03] border border-white/[0.07] rounded-3xl p-6 backdrop-blur-sm shadow-xl flex flex-col justify-between">
      <div>
        <h2 className="text-[10px] font-black uppercase tracking-widest mb-4" style={{ color }}>{title}</h2>
        <div className="text-3xl font-black mb-1 tracking-tighter tabular-nums">{value}</div>
        <p className="text-white/20 text-[10px] font-bold uppercase tracking-widest">{label}</p>
      </div>
      {children}
    </div>
  );
}
