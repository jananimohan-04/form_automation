import { useEffect, useState } from "react";
import {
  Globe,
  Loader2,
  RotateCcw,
  Sparkles,
  Send,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import { api } from "./api";
import Rail from "./components/Rail";
import Panel from "./components/Panel";
import Shot from "./components/Shot";

function useSessionState() {
  const [stage, setStage] = useState("idle");
  const [schema, setSchema] = useState(null);
  const [filledValues, setFilledValues] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const apply = (data) => {
    if (!data) return;
    setStage(data.stage ?? "idle");
    setSchema(data.schema ?? null);
    setFilledValues(data.filledValues ?? {});
    setResult(data.result ?? null);
    setError(data.error ?? null);
  };

  return { stage, schema, filledValues, result, error, setError, apply };
}

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.72rem] font-semibold uppercase tracking-[0.06em] text-ink-faint">{label}</span>
      <span className="text-[0.9rem] text-ink">{children}</span>
    </div>
  );
}

function SchemaTable({ fields }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[0.85rem]">
        <thead>
          <tr className="border-b border-line-soft text-left text-[0.7rem] uppercase tracking-[0.06em] text-ink-faint">
            <th className="px-6 py-2.5 font-semibold">Field</th>
            <th className="px-3 py-2.5 font-semibold">Type</th>
            <th className="px-3 py-2.5 font-semibold">Label</th>
            <th className="px-3 py-2.5 font-semibold">Required</th>
            <th className="px-3 py-2.5 font-semibold">Options</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f, i) => (
            <tr key={i} className="border-b border-line-soft last:border-0 hover:bg-code/40">
              <td className="px-6 py-2.5">
                <code className="chip">{f.name || f.id || "(unnamed)"}</code>
              </td>
              <td className="px-3 py-2.5">
                <span className="pill pill-neutral">{f.type}</span>
                {f.disabled && <span className="pill pill-warn ml-1">disabled</span>}
                {f.readonly && <span className="pill pill-warn ml-1">readonly</span>}
              </td>
              <td className="px-3 py-2.5 text-ink-soft">{f.label || "—"}</td>
              <td className="px-3 py-2.5">{f.required ? <span className="pill pill-warn">required</span> : <span className="text-ink-faint">—</span>}</td>
              <td className="px-3 py-2.5 text-ink-soft">
                {f.options?.length ? f.options.map((o) => o.label).filter(Boolean).join(", ") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FilledTable({ values }) {
  const entries = Object.entries(values || {});
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[0.85rem]">
        <thead>
          <tr className="border-b border-line-soft text-left text-[0.7rem] uppercase tracking-[0.06em] text-ink-faint">
            <th className="px-6 py-2.5 font-semibold">Field</th>
            <th className="px-3 py-2.5 font-semibold">Value used</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, value]) => {
            const text = Array.isArray(value) ? value.join(", ") || "—" : String(value ?? "—");
            const isSkipped = text.startsWith("SKIPPED");
            const isError = text.startsWith("ERROR");
            return (
              <tr key={key} className="border-b border-line-soft last:border-0 hover:bg-code/40">
                <td className="px-6 py-2.5">
                  <code className="chip">{key}</code>
                </td>
                <td className="px-3 py-2.5">
                  {isError ? (
                    <span className="pill pill-err">{text}</span>
                  ) : isSkipped ? (
                    <span className="pill pill-warn">{text}</span>
                  ) : (
                    <span className="text-ink">{text}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const { stage, schema, filledValues, result, error, setError, apply } = useSessionState();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(null); // "detect" | "fill" | "submit" | "reset" | null

  useEffect(() => {
    api.state().then(apply).catch(() => {});
  }, []);

  useEffect(() => {
    if (schema?.url) setUrl(schema.url);
  }, [schema]);

  async function run(action, fn) {
    setBusy(action);
    setError(null);
    try {
      const data = await fn();
      apply(data);
    } catch (e) {
      setError(e.message || "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  const handleDetect = (e) => {
    e.preventDefault();
    if (!url.trim()) {
      setError("Please enter a URL.");
      return;
    }
    run("detect", () => api.detect(url.trim()));
  };

  const handleFill = () => run("fill", () => api.fill());
  const handleSubmit = () => run("submit", () => api.submit());
  const handleReset = () => {
    run("reset", () => api.reset()).then(() => {
      setUrl("");
      apply({ stage: "idle", schema: null, filledValues: {}, result: null, error: null });
    });
  };

  const hasSchema = Boolean(schema);
  const hasFilled = Object.keys(filledValues || {}).length > 0;
  const hasResult = Boolean(result);

  return (
    <div className="flex min-h-screen w-full bg-bg text-ink">
      <Rail stage={stage} />

      <main className="min-w-0 flex-1 px-8 py-10 max-md:px-4">
        <div className="mx-auto max-w-3xl">
          <header className="mb-8">
            <h1 className="text-[1.6rem] font-bold tracking-tight">Dynamic Form Automation</h1>
            <p className="mt-1 text-[0.92rem] text-ink-soft">
              Paste any form URL, then walk through detect &rarr; fill &rarr; submit &mdash; no hardcoded fields.
            </p>
          </header>

          {error && (
            <div className="mb-6 flex items-start gap-2.5 rounded-lg border border-err/30 bg-err-bg px-4 py-3 text-[0.86rem] text-err">
              <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Stage 1: Detect */}
          <Panel
            stageNum={1}
            title="Detect Form"
            badge={
              hasSchema && (
                <span className="pill pill-ok">
                  <CheckCircle2 size={13} /> {schema.field_count} field{schema.field_count === 1 ? "" : "s"}
                </span>
              )
            }
          >
            <form onSubmit={handleDetect} className="flex flex-col gap-3 px-6 py-5">
              <label className="text-[0.8rem] font-semibold text-ink-soft" htmlFor="url">
                Target URL
              </label>
              <div className="flex gap-2.5 max-sm:flex-col">
                <div className="relative flex-1">
                  <Globe size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
                  <input
                    id="url"
                    type="text"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example.com/some-form-page"
                    className="w-full rounded-lg border border-line bg-bg py-2.5 pl-10 pr-3.5 text-[0.9rem] text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-accent"
                  />
                </div>
                <button type="submit" disabled={busy === "detect"} className="btn btn-primary flex items-center justify-center gap-2">
                  {busy === "detect" ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
                  {busy === "detect" ? "Opening…" : "Detect Form"}
                </button>
              </div>
            </form>

            {hasSchema && (
              <>
                <div className="border-t border-line-soft px-6 py-3 text-[0.82rem] text-ink-soft">
                  <span className="font-semibold text-ink">{schema.page_title || schema.url}</span>
                  {" — "}
                  submit button {schema.has_submit_button ? "found" : "not found"}
                </div>
                <div className="border-t border-line-soft">
                  <SchemaTable fields={schema.fields || []} />
                </div>
                <div className="border-t border-line-soft">
                  <Shot src={api.screenshotUrl("before")} caption="Page as loaded, before filling" />
                </div>
              </>
            )}
          </Panel>

          {/* Stage 2: Fill */}
          <Panel
            stageNum={2}
            title="Fill With Fake Data"
            locked={!hasSchema}
            lockedNote="Detect a form first."
            badge={
              hasFilled && (
                <span className="pill pill-ok">
                  <CheckCircle2 size={13} /> filled
                </span>
              )
            }
          >
            <div className="flex items-center justify-between gap-4 px-6 py-5">
              <p className="text-[0.86rem] text-ink-soft">
                Generates realistic values per field type via Faker and types them into the live page.
              </p>
              <button
                onClick={handleFill}
                disabled={busy === "fill"}
                className="btn btn-primary flex flex-shrink-0 items-center justify-center gap-2"
              >
                {busy === "fill" ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                {busy === "fill" ? "Filling…" : "Fill Form"}
              </button>
            </div>
            {hasFilled && (
              <div className="border-t border-line-soft">
                <FilledTable values={filledValues} />
              </div>
            )}
          </Panel>

          {/* Stage 3: Submit */}
          <Panel
            stageNum={3}
            title="Submit &amp; Verify"
            locked={!hasFilled}
            lockedNote="Fill the form first."
            badge={
              hasResult &&
              (result.success_detected ? (
                <span className="pill pill-ok">
                  <CheckCircle2 size={13} /> success
                </span>
              ) : result.error_detected ? (
                <span className="pill pill-err">
                  <XCircle size={13} /> error
                </span>
              ) : (
                <span className="pill pill-warn">
                  <AlertTriangle size={13} /> unclear
                </span>
              ))
            }
          >
            <div className="flex items-center justify-between gap-4 px-6 py-5">
              <p className="text-[0.86rem] text-ink-soft">Submits the form and reads back the resulting page.</p>
              <button
                onClick={handleSubmit}
                disabled={busy === "submit"}
                className="btn btn-primary flex flex-shrink-0 items-center justify-center gap-2"
              >
                {busy === "submit" ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                {busy === "submit" ? "Submitting…" : "Submit Form"}
              </button>
            </div>

            {hasResult && (
              <>
                <div className="grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line-soft px-6 py-5 max-sm:grid-cols-1">
                  <Field label="Submitted">{String(result.submitted)}</Field>
                  <Field label="HTTP Status">{result.http_status_after ?? "—"}</Field>
                  <Field label="Final Title">{result.final_title || "—"}</Field>
                  <Field label="Final URL">
                    <span className="break-all font-mono text-[0.8rem]">{result.final_url || "—"}</span>
                  </Field>
                  {result.success_messages?.length > 0 && (
                    <Field label="Success Messages">{result.success_messages.join(" · ")}</Field>
                  )}
                  {result.error_messages?.length > 0 && (
                    <Field label="Error Messages">{result.error_messages.join(" · ")}</Field>
                  )}
                </div>
                <div className="border-t border-line-soft">
                  <Shot src={api.screenshotUrl("after")} caption="Page after submission" />
                </div>
              </>
            )}
          </Panel>

          {stage !== "idle" && (
            <button
              onClick={handleReset}
              disabled={busy === "reset"}
              className="btn btn-secondary mt-2 flex items-center gap-2"
            >
              {busy === "reset" ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
              Start Over With a New URL
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
