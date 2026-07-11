export default function Panel({ stageNum, title, badge, locked, lockedNote, children }) {
  return (
    <section className={`panel ${locked ? "panel-locked" : ""}`}>
      <div className="flex items-center justify-between gap-4 border-b border-line-soft px-6 py-4">
        <div>
          <p className="mb-0.5 font-mono text-[0.7rem] uppercase tracking-[0.08em] text-ink-faint">
            Stage {stageNum}
          </p>
          <h2 className="text-[1.02rem] font-bold tracking-tight">{title}</h2>
        </div>
        {badge}
      </div>
      {locked ? (
        <p className="px-6 py-5 text-[0.88rem] text-ink-faint">{lockedNote}</p>
      ) : (
        children
      )}
    </section>
  );
}
