import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
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
  FileText,
  Target,
  ClipboardList,
} from "lucide-react";

import { useSpeechRecorder } from "@/hooks/use-speech-recorder";
import { useLiveCoaching } from "@/hooks/use-live-coaching";
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
import type { LiveTip } from "@/lib/api/onfly.functions";

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
type AppMode = "precall" | "onfly";

type ContextCard = "notes" | "goal" | "precall";

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
  const [mode, setMode] = useState<AppMode>("precall");
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
  const [liveContext, setLiveContext] = useState("");
  const [liveSetup, setLiveSetup] = useState("");
  const [liveConsent, setLiveConsent] = useState(false);
  const [liveTts, setLiveTts] = useState(false);
  const [liveInputOpen, setLiveInputOpen] = useState(true);
  const [usePrecallBrief, setUsePrecallBrief] = useState(false);
  const [expandedContext, setExpandedContext] = useState<ContextCard | null>(null);
  const [consentNudge, setConsentNudge] = useState(false);
  const consentRef = useRef<HTMLLabelElement>(null);
  // Each mode keeps its own transcript; the recorder's `transcript` is the
  // active buffer and we swap it in/out when the user changes mode so pre-call
  // text never bleeds into on-fly (and vice-versa).
  const [precallText, setPrecallText] = useState("");
  const [onflyText, setOnflyText] = useState("");
  const live = useLiveCoaching({ transcript, ttsEnabled: liveTts });
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
  const hasPrecall = Boolean(requestId && (brief || facts));
  const canRun = transcript.trim().length > 4 && !isBusy && !blockedByLimit;
  const canStartLiveBase = !isBusy && (recording || transcript.trim().length > 0);

  const onPrimaryAction = async () => {
    if (mode === "precall") {
      await run();
      return;
    }
    if (live.isLive) {
      await live.stop();
      if (recording) stop();
      return;
    }
    if (!liveConsent) {
      setConsentNudge(true);
      setLiveInputOpen(true);
      consentRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setConsentNudge(false);
    if (!recording) start();
    const usePre = usePrecallBrief && hasPrecall;
    await live.start({
      precallRequestId: usePre ? (requestId ?? undefined) : undefined,
      precallBrief: usePre && brief ? JSON.stringify(brief) : undefined,
      precallFacts: usePre && facts ? JSON.stringify(facts) : undefined,
      pastedContext: liveContext,
      spokenSetup: liveSetup,
      ttsEnabled: liveTts,
      maxTips: 1,
    });
  };

  const changeMode = (next: AppMode) => {
    if (next === mode) return;
    if (recording) stop();
    // Stash the current buffer, then load the target mode's own buffer.
    if (mode === "precall") setPrecallText(transcript);
    else setOnflyText(transcript);
    setTranscript(next === "precall" ? precallText : onflyText);
    setMode(next);
  };

  // Auto-enable pre-call context when a brief becomes ready.
  useEffect(() => {
    if (hasPrecall) setUsePrecallBrief(true);
  }, [hasPrecall]);

  // Collapse the on-fly input once a live session is running so the tips lead.
  useEffect(() => {
    if (live.isLive) setLiveInputOpen(false);
    else setLiveInputOpen(true);
  }, [live.isLive]);

  // When the shared limit is exhausted, reveal the keys panel so the user can continue.
  useEffect(() => {
    if (outOfRuns && !keysComplete) setKeysOpen(true);
  }, [outOfRuns, keysComplete]);

  const showLiveInputs = mode === "precall" || !live.isLive || liveInputOpen;

  return (
    <main className="relative z-10 max-w-6xl mx-auto px-4 sm:px-5 md:px-8 py-6 md:py-10">
      {/* GitHub corner — standard top-right source-link ribbon (hidden on phones) */}
      <a
        href="https://github.com/rockramsri/SalesBuff-Pre-Call"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="View SalesBuff source on GitHub"
        className="github-corner hidden sm:block fixed top-0 right-0 z-50"
      >
        <svg width="64" height="64" viewBox="0 0 250 250" aria-hidden="true">
          <path fill="var(--salesbuff-ink)" d="M0,0 L115,115 L250,250 L250,0 Z" />
          <path
            className="octo-arm"
            fill="var(--salesbuff-yellow)"
            style={{ transformOrigin: "130px 106px" }}
            d="M128.3,109.0 C113.8,99.7 119.0,89.6 119.0,89.6 C122.0,82.7 120.5,78.6 120.5,78.6 C119.2,72.0 123.4,76.3 123.4,76.3 C127.3,80.9 125.5,87.3 125.5,87.3 C122.9,97.6 130.6,101.9 134.4,103.2"
          />
          <path
            className="octo-body"
            fill="var(--salesbuff-yellow)"
            d="M115.0,115.0 C114.9,115.1 118.7,116.5 119.8,115.4 L133.7,101.6 C136.9,99.2 139.9,98.4 142.2,98.6 C133.8,88.0 127.5,74.4 143.8,58.0 C148.5,53.4 154.0,51.2 159.7,51.0 C160.3,49.4 163.2,43.6 171.4,40.1 C171.4,40.1 176.1,42.5 178.8,56.2 C183.1,58.6 187.2,61.8 190.9,65.4 C194.5,69.0 197.7,73.2 200.1,77.6 C213.8,80.2 216.3,84.9 216.3,84.9 C212.7,93.1 206.9,96.0 205.4,96.6 C205.1,102.4 203.0,107.8 198.3,112.5 C181.9,128.9 168.3,122.5 157.7,114.1 C157.9,116.9 156.7,120.9 152.7,124.9 L141.0,136.5 C139.8,137.7 141.6,141.9 141.8,141.8 Z"
          />
        </svg>
      </a>

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
          <a
            href="https://github.com/rockramsri/SalesBuff-Pre-Call"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View SalesBuff on GitHub"
            title="View source on GitHub"
            className="sm:hidden shrink-0 p-1.5 rounded-md text-[var(--salesbuff-ink-soft)] hover:text-[var(--salesbuff-ink)] transition-colors"
          >
            <GitHubMark size={20} />
          </a>
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
            onClick={() => void onPrimaryAction()}
            disabled={mode === "precall" ? !canRun : !live.isLive && !canStartLiveBase}
            className="btn-yellow flex-1 justify-center md:flex-none"
            aria-label={mode === "precall" ? "Run due diligence" : "Toggle live coach"}
          >
            {isBusy ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <Play size={18} fill="currentColor" />
            )}
            <span className="whitespace-nowrap">
              {mode === "precall"
                ? "Run due diligence"
                : live.isLive
                  ? "End live coach"
                  : "Start live coach"}
            </span>
          </button>
        </div>
      </header>

      {/* Live voice waveform — only while speaking */}
      {recording && <VoiceBar analyserRef={analyserRef} />}

      <ModeSwitch mode={mode} onChange={changeMode} />

      {/* Query zone */}
      <section className="mt-6 skeuo-panel p-5 md:p-6">
        {mode === "onfly" && live.isLive && (
          <button
            type="button"
            onClick={() => setLiveInputOpen((o) => !o)}
            className="flex w-full items-center justify-between text-xs uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)]"
          >
            <span>Live transcript &amp; context</span>
            <ChevronDown
              size={16}
              className={`transition-transform ${liveInputOpen ? "rotate-180" : ""}`}
            />
          </button>
        )}
        {showLiveInputs && (
          <>
            <div
              className={`flex items-center justify-between mb-3 ${mode === "onfly" && live.isLive ? "mt-4" : ""}`}
            >
              <label
                htmlFor="prompt"
                className="text-xs uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)]"
              >
                {mode === "precall" ? "Account scenario" : "Live transcript"}
              </label>
              <div className="text-xs text-muted-foreground">
                {mode === "precall"
                  ? "Speak your account scenario, then edit before running."
                  : "Speak naturally. SalesBuff will coach from finalized chunks."}
              </div>
            </div>
            <textarea
              id="prompt"
              className="skeuo-textarea"
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder={
                mode === "precall"
                  ? "e.g. Meeting with Dr. Sarah Chen at Mount Sinai tomorrow. They use McKesson today and I want to talk supply chain reliability."
                  : "Live transcript appears here while you speak..."
              }
              disabled={isBusy}
            />
            {micError && <p className="mt-2 text-sm text-[oklch(0.8_0.15_60)]">{micError}</p>}
            {errorMsg && <p className="mt-2 text-sm text-destructive">{errorMsg}</p>}
            {blockedByLimit && !errorMsg && (
              <p className="mt-2 text-sm text-destructive">
                You've used all {usage?.limit} shared runs — add your own API keys below to
                continue.
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

            {mode === "onfly" && (
              <LiveSetupPanel
                hasPrecall={hasPrecall}
                context={liveContext}
                setup={liveSetup}
                consent={liveConsent}
                tts={liveTts}
                usePrecallBrief={usePrecallBrief}
                expanded={expandedContext}
                consentNudge={consentNudge}
                consentRef={consentRef}
                onContextChange={setLiveContext}
                onSetupChange={setLiveSetup}
                onConsentChange={(v) => {
                  setLiveConsent(v);
                  if (v) setConsentNudge(false);
                }}
                onTtsChange={setLiveTts}
                onUsePrecallChange={setUsePrecallBrief}
                onExpand={setExpandedContext}
                onGoPrecall={() => changeMode("precall")}
              />
            )}
          </>
        )}
      </section>

      {/* Status / Results */}
      <section className="mt-8 min-h-[160px]">
        {mode === "onfly" ? (
          <LiveCoachPanel
            phase={live.phase}
            tips={live.tips}
            error={live.error}
            isLive={live.isLive}
          />
        ) : (
          <>
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
          </>
        )}
      </section>

      {/* Floating one-tap tip button — always reachable mid-call, no scrolling */}
      {mode === "onfly" && (
        <button
          type="button"
          onClick={() => void live.requestTipNow()}
          disabled={!live.isLive}
          title={live.isLive ? "Get a coaching tip now" : "Start a live session to use this"}
          className="btn-yellow fixed bottom-5 right-5 z-50 px-6 py-4 text-base shadow-xl rounded-full"
          aria-label="Get a coaching tip now"
        >
          <Sparkles size={18} />
          Get tip now
        </button>
      )}
    </main>
  );
}

function GitHubMark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

function ModeSwitch({ mode, onChange }: { mode: AppMode; onChange: (mode: AppMode) => void }) {
  const base =
    "flex-1 px-4 py-2.5 text-sm font-bold uppercase tracking-wider rounded-md transition-colors";
  const active = "bg-[var(--salesbuff-ink)] text-[var(--salesbuff-yellow)]";
  const idle = "text-[var(--salesbuff-ink-soft)] hover:text-[var(--salesbuff-ink)]";
  return (
    <div className="mt-4 skeuo-inset p-1 flex gap-1 max-w-md mx-auto">
      <button
        type="button"
        onClick={() => onChange("precall")}
        className={`${base} ${mode === "precall" ? active : idle}`}
      >
        Pre-call
      </button>
      <button
        type="button"
        onClick={() => onChange("onfly")}
        className={`${base} ${mode === "onfly" ? active : idle}`}
      >
        On-fly
      </button>
    </div>
  );
}

function LiveSetupPanel({
  hasPrecall,
  context,
  setup,
  consent,
  tts,
  usePrecallBrief,
  expanded,
  consentNudge,
  consentRef,
  onContextChange,
  onSetupChange,
  onConsentChange,
  onTtsChange,
  onUsePrecallChange,
  onExpand,
  onGoPrecall,
}: {
  hasPrecall: boolean;
  context: string;
  setup: string;
  consent: boolean;
  tts: boolean;
  usePrecallBrief: boolean;
  expanded: ContextCard | null;
  consentNudge: boolean;
  consentRef: RefObject<HTMLLabelElement | null>;
  onContextChange: (value: string) => void;
  onSetupChange: (value: string) => void;
  onConsentChange: (value: boolean) => void;
  onTtsChange: (value: boolean) => void;
  onUsePrecallChange: (value: boolean) => void;
  onExpand: (card: ContextCard | null) => void;
  onGoPrecall: () => void;
}) {
  const toggle = (card: ContextCard) => onExpand(expanded === card ? null : card);

  const onPrecallClick = () => {
    if (!hasPrecall) {
      onGoPrecall();
      return;
    }
    toggle("precall");
  };

  return (
    <div className="mt-5 border-t border-dashed border-[oklch(0.7_0.05_75/0.5)] pt-4 space-y-4">
      <div className="text-xs font-bold uppercase tracking-wider text-[var(--salesbuff-ink-soft)]">
        Optional context — pick what to add
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <ContextOptionCard
          icon={<FileText size={18} />}
          title="Paste notes"
          hint={context.trim() ? "Notes added" : "CRM, agenda, stakeholders"}
          active={expanded === "notes"}
          filled={Boolean(context.trim())}
          onClick={() => toggle("notes")}
        />
        <ContextOptionCard
          icon={<Target size={18} />}
          title="Call goal"
          hint={setup.trim() ? "Goal set" : "What you want from this call"}
          active={expanded === "goal"}
          filled={Boolean(setup.trim())}
          onClick={() => toggle("goal")}
        />
        <ContextOptionCard
          icon={<ClipboardList size={18} />}
          title="Pre-call brief"
          hint={
            hasPrecall
              ? usePrecallBrief
                ? "✓ Brief attached"
                : "Brief ready — tap to attach"
              : "Run a pre-call first"
          }
          active={expanded === "precall"}
          filled={hasPrecall && usePrecallBrief}
          onClick={onPrecallClick}
        />
      </div>

      {expanded === "notes" && (
        <textarea
          value={context}
          onChange={(e) => onContextChange(e.target.value)}
          className="skeuo-textarea min-h-[90px]"
          placeholder="Paste CRM notes, agenda, stakeholder context, or anything the live coach should know..."
          autoFocus
        />
      )}
      {expanded === "goal" && (
        <input
          value={setup}
          onChange={(e) => onSetupChange(e.target.value)}
          className="w-full rounded-md border-2 border-[oklch(0.8_0.05_85)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--salesbuff-ink)]"
          placeholder="What are you trying to accomplish on this call?"
          autoFocus
        />
      )}
      {expanded === "precall" && hasPrecall && (
        <label className="flex gap-2 items-start text-sm text-[var(--salesbuff-ink)] skeuo-inset p-3">
          <input
            type="checkbox"
            checked={usePrecallBrief}
            onChange={(e) => onUsePrecallChange(e.target.checked)}
            className="mt-1"
          />
          <span>
            Attach your completed pre-call brief (Actions + Facts) as background context for live
            coaching.
          </span>
        </label>
      )}

      <label
        ref={consentRef}
        className={`flex gap-2 items-start text-sm text-[var(--salesbuff-ink)] rounded-md p-2 -mx-2 transition-shadow ${
          consentNudge
            ? "consent-nudge ring-2 ring-[var(--salesbuff-yellow)] bg-[oklch(0.97_0.04_95)]"
            : ""
        }`}
      >
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => onConsentChange(e.target.checked)}
          className="mt-1"
        />
        <span>
          {consentNudge && (
            <span className="block font-bold text-[var(--salesbuff-ink)] mb-1">
              Enable this to start live coaching →
            </span>
          )}
          I have permission to listen to / transcribe this conversation, and I am responsible for
          any required customer disclosure.
        </span>
      </label>
      <label className="flex gap-2 items-center text-sm text-[var(--salesbuff-ink-soft)]">
        <input type="checkbox" checked={tts} onChange={(e) => onTtsChange(e.target.checked)} />
        Speak accepted tips aloud in this browser
      </label>
    </div>
  );
}

function ContextOptionCard({
  icon,
  title,
  hint,
  active,
  filled,
  onClick,
}: {
  icon: ReactNode;
  title: string;
  hint: string;
  active: boolean;
  filled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`skeuo-card w-full text-left p-3 transition-all ${active ? "translate-x-[-1px] translate-y-[-1px]" : ""}`}
      data-expanded={active}
    >
      <div className="flex items-start gap-2">
        <span className="text-[var(--salesbuff-ink)] shrink-0 mt-0.5">{icon}</span>
        <div className="min-w-0">
          <div className="font-bold text-sm text-[var(--salesbuff-ink)]">{title}</div>
          <div
            className={`text-xs mt-0.5 truncate ${filled ? "text-[oklch(0.55_0.15_150)] font-semibold" : "text-[var(--salesbuff-ink-soft)]"}`}
          >
            {hint}
          </div>
        </div>
      </div>
    </button>
  );
}

function LiveCoachPanel({
  phase,
  tips,
  error,
  isLive,
}: {
  phase: string;
  tips: LiveTip[];
  error: string | null;
  isLive: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)]">
        <Sparkles size={14} />
        {isLive
          ? phase === "starting"
            ? "Starting…"
            : "Listening — coaching live"
          : "On-fly live coach"}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {!isLive && tips.length === 0 ? (
        <div className="skeuo-panel p-8 text-center">
          <div className="text-sm uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)] mb-2">
            Press “Start live coach” to begin
          </div>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Add any context, give consent, then start. SalesBuff listens and shows one short action
            line when the moment is right.
          </p>
        </div>
      ) : tips.length === 0 ? (
        <div className="skeuo-panel p-8 text-center">
          <div className="text-sm uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)] mb-2">
            Waiting for a useful moment
          </div>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Once the call has enough signal, SalesBuff will show one short action line. Weak or
            repeated advice is filtered out.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {tips.map((tip) => (
            <LiveTipCard key={tip.tip_id} tip={tip} />
          ))}
        </div>
      )}
    </div>
  );
}

function LiveTipCard({ tip }: { tip: LiveTip }) {
  const [reasonOpen, setReasonOpen] = useState(false);
  return (
    <article className="skeuo-card p-5">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="pill pill-category">
            {tip.source === "background" ? "Research-backed" : "Live"}
          </span>
          {tip.tip_type && tip.tip_type !== "other" && (
            <span className="pill pill-confidence">{tip.tip_type.replace(/_/g, " ")}</span>
          )}
          {tip.stage && (
            <span className="text-[0.65rem] uppercase tracking-wider font-bold text-muted-foreground/70">
              {tip.stage.replace(/_/g, " ")}
            </span>
          )}
        </div>
        <span className="text-[0.7rem] uppercase tracking-wider font-bold text-muted-foreground">
          {tip.confidence}
        </span>
      </div>
      <p className="font-display text-lg font-bold leading-snug text-[var(--salesbuff-ink)]">
        {tip.action_sentence}
      </p>
      {tip.trigger && (
        <p className="text-sm text-[var(--salesbuff-ink-soft)] mt-3">Trigger: {tip.trigger}</p>
      )}
      {tip.reason && (
        <div className="mt-3 border-t border-dashed border-[oklch(0.7_0.05_75/0.4)] pt-2">
          <button
            type="button"
            onClick={() => setReasonOpen((o) => !o)}
            className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-[var(--salesbuff-ink-soft)] hover:text-[var(--salesbuff-ink)]"
          >
            Why this
            <ChevronDown
              size={14}
              className={`transition-transform ${reasonOpen ? "rotate-180" : ""}`}
            />
          </button>
          {reasonOpen && (
            <p className="text-sm text-[var(--salesbuff-ink-soft)] mt-2 leading-relaxed">
              {tip.reason}
            </p>
          )}
        </div>
      )}
    </article>
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
