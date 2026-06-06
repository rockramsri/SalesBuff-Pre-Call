import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import {
  Loader2,
  Play,
  Sparkles,
  RotateCcw,
  Key,
  ChevronDown,
  Info,
  ExternalLink,
} from "lucide-react";

import { useSpeechRecorder } from "@/hooks/use-speech-recorder";
import { RecordButton } from "@/components/salesbuff/RecordButton";
import { VoiceBar } from "@/components/salesbuff/VoiceBar";
import { ResultsHeader } from "@/components/salesbuff/ResultsHeader";
import { CardList } from "@/components/salesbuff/CardList";
import { FactsView } from "@/components/salesbuff/FactsView";
import {
  getResearch,
  getUsage,
  submitResearch,
  type FactsReport,
  type SalesBrief,
  type Usage,
} from "@/lib/api/research.functions";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SalesBuff — Pre-call due diligence in one click" },
      {
        name: "description",
        content:
          "Speak your account scenario, edit the transcript, and get an actionable sales brief in seconds.",
      },
      { property: "og:title", content: "SalesBuff — Pre-call due diligence" },
      {
        property: "og:description",
        content: "One-shot account research for sales reps. Speak, edit, run.",
      },
    ],
  }),
  component: SalesBuffApp,
});

type Phase = "idle" | "submitting" | "polling" | "ready" | "error";

function SalesBuffApp() {
  const {
    recording,
    transcript,
    setTranscript,
    start,
    stop,
    error: micError,
    analyserRef,
  } = useSpeechRecorder();
  const submit = useServerFn(submitResearch);
  const fetchJob = useServerFn(getResearch);
  const fetchUsage = useServerFn(getUsage);
  const [usage, setUsage] = useState<Usage | null>(null);

  const refreshUsage = useCallback(async () => {
    try {
      setUsage(await fetchUsage());
    } catch {
      /* usage is non-critical; ignore fetch errors */
    }
  }, [fetchUsage]);

  useEffect(() => {
    refreshUsage();
  }, [refreshUsage]);

  const [phase, setPhase] = useState<Phase>("idle");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [brief, setBrief] = useState<SalesBrief | null>(null);
  const [facts, setFacts] = useState<FactsReport | null>(null);
  const [tab, setTab] = useState<"actions" | "facts">("actions");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Own-API-keys (memory only — never persisted).
  const [keys, setKeys] = useState({ openai: "", tavily: "", courtlistener: "" });
  const [keysOpen, setKeysOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [stage, setStage] = useState<string>("queued");
  const [progress, setProgress] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const onRecord = () => (recording ? stop() : start());

  const clearTimers = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (tickRef.current) clearInterval(tickRef.current);
    pollRef.current = null;
    tickRef.current = null;
  };

  useEffect(() => () => clearTimers(), []);

  const run = useCallback(async () => {
    if (!transcript.trim()) return;
    if (recording) stop();
    setErrorMsg(null);
    setBrief(null);
    setFacts(null);
    setTab("actions");
    setElapsed(0);
    setStage("queued");
    setProgress(0);
    setPhase("submitting");
    try {
      const ownKeys =
        keys.openai.trim() && keys.tavily.trim()
          ? {
              openai: keys.openai.trim(),
              tavily: keys.tavily.trim(),
              courtlistener: keys.courtlistener.trim() || undefined,
            }
          : undefined;
      const { request_id, usage: u } = await submit({
        data: { prompt: transcript.trim(), keys: ownKeys },
      });
      setRequestId(request_id);
      if (u) setUsage(u);
      setPhase("polling");
      tickRef.current = setInterval(() => setElapsed((s) => s + 1), 100);
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetchJob({ data: { id: request_id } });
          if (res.status === "completed") {
            clearTimers();
            if (res.brief || res.facts) {
              setBrief(res.brief);
              setFacts(res.facts);
              setTab(res.brief ? "actions" : "facts");
              setPhase("ready");
            } else {
              setErrorMsg(
                res.warnings[0] ?? "Couldn't generate a brief from the available findings.",
              );
              setPhase("error");
            }
          } else if (res.status === "failed") {
            clearTimers();
            setErrorMsg(res.error);
            setPhase("error");
          } else if (res.status === "not_found") {
            clearTimers();
            setErrorMsg("Research job not found.");
            setPhase("error");
          } else {
            setStage(res.stage);
            setProgress(res.progress);
          }
        } catch (e) {
          clearTimers();
          setErrorMsg(e instanceof Error ? e.message : "Polling failed");
          setPhase("error");
        }
      }, 1000);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Submission failed");
      setPhase("error");
      void refreshUsage();
    }
  }, [transcript, recording, stop, submit, fetchJob, refreshUsage, keys]);

  const reset = () => {
    clearTimers();
    setBrief(null);
    setFacts(null);
    setTab("actions");
    setRequestId(null);
    setErrorMsg(null);
    setPhase("idle");
    setElapsed(0);
    setStage("queued");
    setProgress(0);
  };

  const isBusy = phase === "submitting" || phase === "polling";
  const outOfRuns = usage !== null && usage.remaining <= 0;
  const keysComplete = keys.openai.trim().length > 0 && keys.tavily.trim().length > 0;
  // Out of shared runs is fine as long as the user brought their own keys.
  const blockedByLimit = outOfRuns && !keysComplete;
  const canRun = transcript.trim().length > 4 && !isBusy && !blockedByLimit;

  // When the shared limit is exhausted, reveal the keys panel so the user can continue.
  useEffect(() => {
    if (outOfRuns && !keysComplete) setKeysOpen(true);
  }, [outOfRuns, keysComplete]);

  return (
    <main className="relative z-10 max-w-6xl mx-auto px-4 sm:px-5 md:px-8 py-6 md:py-10">
      {/* Top bar */}
      <header className="skeuo-panel px-4 md:px-7 py-4 md:py-5 flex flex-col gap-4 md:flex-row md:items-center md:gap-5">
        {/* Brand row (usage badge sits beside brand on mobile) */}
        <div className="flex items-center gap-3 min-w-0">
          <img
            src="/salesbuff-icon.png"
            alt="SalesBuff"
            width={44}
            height={44}
            className="brand-mark shrink-0"
          />
          <div className="min-w-0">
            <div className="font-display text-2xl md:text-[28px] font-black tracking-tight leading-none text-ink uppercase">
              SalesBuff
            </div>
            <div className="text-xs text-ink-soft mt-1 truncate font-semibold">
              Pre-call due diligence, in one breath.
            </div>
          </div>
          {usage && (
            <div className="ml-auto md:hidden">
              <UsageBadge usage={usage} />
            </div>
          )}
        </div>

        <div className="hidden md:block md:flex-1" />

        {/* Controls row */}
        <div className="flex items-center justify-between gap-3 md:justify-end md:gap-5">
          {usage && (
            <div className="hidden md:block">
              <UsageBadge usage={usage} />
            </div>
          )}
          <div className="hidden md:flex flex-col items-end">
            <div className="text-xs uppercase tracking-wider font-bold text-muted-foreground">
              {recording ? "Listening…" : "Hold the floor"}
            </div>
            <div className="text-[0.7rem] text-muted-foreground/70">
              Tap to {recording ? "stop" : "record"} your scenario
            </div>
          </div>
          <RecordButton recording={recording} onClick={onRecord} disabled={isBusy} />
          <button
            type="button"
            onClick={run}
            disabled={!canRun}
            className="btn-yellow flex-1 justify-center md:flex-none"
            aria-label="Run due diligence"
          >
            {isBusy ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <Play size={18} fill="currentColor" />
            )}
            <span className="whitespace-nowrap">Run due diligence</span>
          </button>
        </div>
      </header>

      {/* Live voice waveform — only while speaking */}
      {recording && <VoiceBar analyserRef={analyserRef} />}

      {/* Query zone */}
      <section className="mt-6 skeuo-panel p-5 md:p-6">
        <div className="flex items-center justify-between mb-3">
          <label
            htmlFor="prompt"
            className="text-xs uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)]"
          >
            Account scenario
          </label>
          <div className="text-xs text-muted-foreground">
            Speak your account scenario, then edit before running.
          </div>
        </div>
        <textarea
          id="prompt"
          className="skeuo-textarea"
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="e.g. Meeting with Dr. Sarah Chen at Mount Sinai tomorrow. They use McKesson today and I want to talk supply chain reliability."
          disabled={isBusy}
        />
        {micError && <p className="mt-2 text-sm text-[oklch(0.8_0.15_60)]">{micError}</p>}
        {errorMsg && <p className="mt-2 text-sm text-destructive">{errorMsg}</p>}
        {blockedByLimit && !errorMsg && (
          <p className="mt-2 text-sm text-destructive">
            You've used all {usage?.limit} shared runs — add your own API keys below to continue.
          </p>
        )}

        <div className="mt-4 border-t border-dashed border-[oklch(0.7_0.05_75/0.5)] pt-3">
          <button
            type="button"
            onClick={() => setKeysOpen((o) => !o)}
            className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[var(--salesbuff-ink-soft)] hover:text-[var(--salesbuff-ink)]"
          >
            <Key size={13} />
            Use my own API keys
            {keysComplete && <span className="text-[oklch(0.55_0.15_150)]">• active</span>}
            <ChevronDown
              size={14}
              className={`transition-transform ${keysOpen ? "rotate-180" : ""}`}
            />
          </button>

          {keysOpen && <KeysPanel keys={keys} onChange={setKeys} disabled={isBusy} />}
        </div>
      </section>

      {/* Status / Results */}
      <section className="mt-8 min-h-[160px]">
        {phase === "idle" && <EmptyState />}

        {isBusy && <ResearchingState elapsed={elapsed} stage={stage} progress={progress} />}

        {phase === "ready" && (brief || facts) && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="text-xs uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)] flex items-center gap-2">
                <Sparkles size={14} /> Brief ready
                <span className="text-[var(--salesbuff-ink-soft)] normal-case tracking-normal font-normal">
                  · {new Date((brief ?? facts!).generated_at).toLocaleTimeString()}
                </span>
              </div>
              <button type="button" onClick={reset} className="btn-ghost">
                <RotateCcw size={14} /> New brief
              </button>
            </div>

            {brief && <ResultsHeader brief={brief} />}

            <TabSwitch tab={tab} onChange={setTab} />

            {tab === "actions" &&
              (brief ? (
                <div className="space-y-6">
                  {brief.next_step_line && <NextStepCallout text={brief.next_step_line} />}
                  <CardList brief={brief} />
                </div>
              ) : (
                <EmptyLane label="No action coach could be generated for this account." />
              ))}

            {tab === "facts" &&
              (facts ? (
                <FactsView facts={facts} />
              ) : (
                <EmptyLane label="No evidence dossier could be generated for this account." />
              ))}

            {requestId && (
              <p className="text-center text-[0.7rem] text-muted-foreground/60 pt-4">
                request_id · {requestId}
              </p>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

function UsageBadge({ usage }: { usage: Usage }) {
  const pct = usage.limit > 0 ? Math.min(100, (usage.used / usage.limit) * 100) : 0;
  const out = usage.remaining <= 0;
  return (
    <div
      className="skeuo-card px-3 py-2 flex flex-col gap-1 min-w-[88px] md:min-w-[120px]"
      title={`${usage.used} of ${usage.limit} shared runs used`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[0.6rem] uppercase tracking-wider font-bold text-muted-foreground">
          Runs left
        </span>
        <span
          className={`font-display text-sm font-black ${out ? "text-destructive" : "text-foreground"}`}
        >
          {usage.remaining}
          <span className="text-muted-foreground font-normal">/{usage.limit}</span>
        </span>
      </div>
      <div className="skeuo-inset h-1.5 overflow-hidden">
        <div
          className="h-full transition-[width] duration-300"
          style={{
            width: `${pct}%`,
            background: out
              ? "oklch(0.62 0.24 28)"
              : "linear-gradient(90deg, oklch(0.86 0.18 92), oklch(0.7 0.18 75))",
          }}
        />
      </div>
    </div>
  );
}

type KeyState = { openai: string; tavily: string; courtlistener: string };

function HelpLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-0.5 font-bold text-[var(--salesbuff-ink)] underline underline-offset-2 break-all"
    >
      {children}
      <ExternalLink size={10} className="shrink-0" />
    </a>
  );
}

function KeyHelp({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={`How to get your ${label}`}
        onClick={() => setOpen((o) => !o)}
        className="key-help-btn"
      >
        <Info size={13} />
      </button>
      {open && (
        <div className="key-help-pop" role="tooltip">
          <div className="key-help-title">How to get your {label}</div>
          {children}
        </div>
      )}
    </span>
  );
}

const KEY_HELP: Record<keyof KeyState, ReactNode> = {
  openai: (
    <ol className="key-help-steps">
      <li>
        Sign in at{" "}
        <HelpLink href="https://platform.openai.com/api-keys">
          platform.openai.com/api-keys
        </HelpLink>
        .
      </li>
      <li>
        Click <b>Create new secret key</b> and copy the <code>sk-…</code> value (shown only once).
      </li>
      <li>
        Add a little credit under <b>Billing</b> — the key needs funds to run.
      </li>
    </ol>
  ),
  tavily: (
    <ol className="key-help-steps">
      <li>
        Sign up at <HelpLink href="https://app.tavily.com/home">app.tavily.com</HelpLink>.
      </li>
      <li>
        Copy the key (starts with <code>tvly-</code>) from your dashboard / API Keys.
      </li>
      <li>Free tier = 1,000 credits/month, no card needed.</li>
    </ol>
  ),
  courtlistener: (
    <ol className="key-help-steps">
      <li>
        Register or sign in:{" "}
        <HelpLink href="https://www.courtlistener.com/sign-in/">courtlistener.com/sign-in</HelpLink>
        .
      </li>
      <li>
        Grab your token:{" "}
        <HelpLink href="https://www.courtlistener.com/profile/api-token/">
          courtlistener.com/profile/api-token
        </HelpLink>
        .
      </li>
      <li>Optional — only enables court-record lookups.</li>
    </ol>
  ),
};

function KeysPanel({
  keys,
  onChange,
  disabled,
}: {
  keys: KeyState;
  onChange: (k: KeyState) => void;
  disabled: boolean;
}) {
  const field = (id: keyof KeyState, label: string, placeholder: string, optional = false) => (
    <div className="space-y-1">
      <label
        htmlFor={id}
        className="flex items-center gap-1.5 text-[0.7rem] uppercase tracking-wider font-bold text-muted-foreground"
      >
        <span>
          {label} {optional && <span className="font-normal normal-case">(optional)</span>}
        </span>
        <KeyHelp label={label}>{KEY_HELP[id]}</KeyHelp>
      </label>
      <input
        id={id}
        type="password"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        value={keys[id]}
        onChange={(e) => onChange({ ...keys, [id]: e.target.value })}
        placeholder={placeholder}
        className="w-full rounded-md border-2 border-[oklch(0.8_0.05_85)] bg-white px-3 py-2 text-sm font-mono outline-none focus:border-[var(--salesbuff-ink)]"
      />
    </div>
  );

  return (
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      {field("openai", "OpenAI key", "sk-...")}
      {field("tavily", "Tavily key", "tvly-...")}
      {field("courtlistener", "CourtListener token", "token", true)}
      <p className="sm:col-span-2 text-[0.7rem] text-muted-foreground">
        Keys are kept in this browser tab only (never saved) and used just for your runs. With your
        own keys, runs don't count against the shared limit.
      </p>
    </div>
  );
}

function TabSwitch({
  tab,
  onChange,
}: {
  tab: "actions" | "facts";
  onChange: (t: "actions" | "facts") => void;
}) {
  const base =
    "flex-1 px-4 py-2.5 text-sm font-bold uppercase tracking-wider rounded-md transition-colors";
  const active = "bg-[var(--salesbuff-ink)] text-[var(--salesbuff-yellow)]";
  const idle = "text-[var(--salesbuff-ink-soft)] hover:text-[var(--salesbuff-ink)]";
  return (
    <div className="skeuo-inset p-1 flex gap-1 max-w-sm mx-auto">
      <button
        type="button"
        onClick={() => onChange("actions")}
        className={`${base} ${tab === "actions" ? active : idle}`}
      >
        Actions
      </button>
      <button
        type="button"
        onClick={() => onChange("facts")}
        className={`${base} ${tab === "facts" ? active : idle}`}
      >
        Facts
      </button>
    </div>
  );
}

function NextStepCallout({ text }: { text: string }) {
  return (
    <div className="skeuo-callout p-4">
      <div className="text-[0.7rem] uppercase tracking-[0.18em] font-bold text-[oklch(0.35_0.1_60)] mb-1">
        Ask for this next step
      </div>
      <p className="font-display text-lg leading-snug font-semibold text-[var(--salesbuff-ink)]">
        {text}
      </p>
    </div>
  );
}

function EmptyLane({ label }: { label: string }) {
  return <div className="skeuo-panel p-8 text-center text-muted-foreground">{label}</div>;
}

function EmptyState() {
  return (
    <div className="skeuo-panel p-8 text-center">
      <div className="text-sm uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)] mb-2">
        Ready when you are
      </div>
      <p className="text-muted-foreground max-w-xl mx-auto">
        Hit the amber button, describe the account in your own words, then run the brief. SalesBuff
        returns a skim-ready stack of action tips plus a sourced fact dossier — no chat, no fluff.
      </p>
    </div>
  );
}

const STAGE_LABEL: Record<string, string> = {
  queued: "Queued…",
  resolving: "Identifying the company, contact & incumbent…",
  researching: "Scanning news, web & court records…",
  briefing: "Writing your card brief…",
  done: "Finishing up…",
};

function ResearchingState({
  elapsed,
  stage,
  progress,
}: {
  elapsed: number;
  stage: string;
  progress: number;
}) {
  const seconds = (elapsed / 10).toFixed(1);
  // Backend milestones drive the bar; a small time-based creep keeps it alive
  // within a stage without ever jumping ahead of the next milestone.
  const creep = Math.min(8, elapsed * 0.03);
  const width = Math.min(97, Math.max(progress, 3) + (stage === "done" ? 0 : creep));
  return (
    <div className="skeuo-panel p-8 text-center">
      <div className="inline-flex items-center gap-3 text-yellow font-display text-xl font-bold">
        <Loader2 className="animate-spin" size={22} />
        {STAGE_LABEL[stage] ?? "Researching…"}
      </div>
      <p className="text-muted-foreground mt-2 text-sm">
        Deep research runs across multiple sources — this can take a minute.{" "}
        <span className="tabular-nums">{seconds}s</span>
      </p>
      <div className="mt-5 max-w-md mx-auto skeuo-inset h-2 overflow-hidden">
        <div
          className="h-full"
          style={{
            width: `${width}%`,
            background: "linear-gradient(90deg, oklch(0.86 0.18 92), oklch(0.7 0.18 75))",
            transition: "width 400ms ease",
            boxShadow: "0 0 12px oklch(0.86 0.18 92 / 0.6)",
          }}
        />
      </div>
    </div>
  );
}
