const STEPS = [
  { key: "detect", label: "Detect", desc: "Open the page, map every field" },
  { key: "fill", label: "Fill", desc: "Generate & type realistic data" },
  { key: "submit", label: "Submit", desc: "Post it & read the response" },
];

function stepStatus(key, stage) {
  const order = { idle: 0, detected: 1, filled: 2, submitted: 3 };
  const current = order[stage] ?? 0;
  const index = { detect: 1, fill: 2, submit: 3 }[key];
  if (current >= index) return "done";
  if (current === index - 1) return "active";
  return "pending";
}

export default function Rail({ stage }) {
  return (
    <aside className="sticky top-0 flex h-screen w-60 flex-shrink-0 flex-col gap-8 overflow-y-auto bg-rail px-5 py-7 max-md:static max-md:h-auto max-md:w-full">
      <div className="flex items-center gap-2.5">
        <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-[7px] bg-gradient-to-br from-accent to-[#1c6fa8] shadow-[0_2px_10px_-2px_var(--accent)]">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
            <path d="M4 6h16M4 12h10M4 18h13" stroke="white" strokeWidth="2" strokeLinecap="round" />
            <circle cx="20" cy="18" r="2" fill="white" />
          </svg>
        </div>
        <div className="leading-tight">
          <div className="text-[0.98rem] font-bold tracking-tight text-rail-ink">Form Automation</div>
          <div className="text-[0.72rem] uppercase tracking-[0.08em] text-rail-ink-dim">Console</div>
        </div>
      </div>

      <nav className="flex flex-col">
        {STEPS.map((step, i) => {
          const status = stepStatus(step.key, stage);
          return (
            <div key={step.key} className="relative flex gap-3 rounded-lg px-2 py-2.5">
              {i < STEPS.length - 1 && (
                <div className="absolute bottom-[-0.6rem] left-[1.15rem] top-[2.3rem] w-px bg-rail-line" />
              )}
              <div
                className={`z-10 grid h-6.5 w-6.5 flex-shrink-0 place-items-center rounded-full border font-mono text-[0.78rem] font-bold transition-all
                  ${
                    status === "done"
                      ? "border-ok bg-ok text-[#06281b]"
                      : status === "active"
                        ? "border-accent bg-accent text-accent-ink shadow-[0_0_0_3px_var(--accent-soft)]"
                        : "border-rail-line bg-rail text-rail-ink-dim"
                  }`}
                style={{ width: "1.6rem", height: "1.6rem" }}
              >
                {status === "done" ? "✓" : i + 1}
              </div>
              <div>
                <div className={`text-[0.86rem] font-semibold ${status === "pending" ? "text-rail-ink-dim" : "text-rail-ink"}`}>
                  {step.label}
                </div>
                <div className="mt-0.5 text-[0.74rem] leading-snug text-rail-ink-dim">{step.desc}</div>
              </div>
            </div>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-rail-line pt-4 text-[0.72rem] leading-relaxed text-rail-ink-dim">
        Live browser session held in memory.
        <br />
        Screenshots &amp; logs land in <code className="font-mono">output/</code>.
      </div>
    </aside>
  );
}
