import { useCallback, useEffect, useRef, useState } from "react";
import { useServerFn } from "@tanstack/react-start";

import {
  createLiveSession,
  endLiveSession,
  getLiveEventsUrl,
  sendLiveChunk,
  type LiveTip,
} from "@/lib/api/onfly.functions";

type LivePhase = "idle" | "starting" | "listening" | "ending" | "error";

type StartLiveOptions = {
  precallRequestId?: string;
  pastedContext?: string;
  spokenSetup?: string;
  precallBrief?: string;
  precallFacts?: string;
  maxTips?: number;
  ttsEnabled?: boolean;
};

export function useLiveCoaching({
  transcript,
  ttsEnabled,
}: {
  transcript: string;
  ttsEnabled: boolean;
}) {
  const createSession = useServerFn(createLiveSession);
  const postChunk = useServerFn(sendLiveChunk);
  const closeSession = useServerFn(endLiveSession);
  const fetchEventsUrl = useServerFn(getLiveEventsUrl);

  const [phase, setPhase] = useState<LivePhase>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [tips, setTips] = useState<LiveTip[]>([]);
  const [error, setError] = useState<string | null>(null);
  const sentOffsetRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const transcriptRef = useRef(transcript);
  const ttsRef = useRef(ttsEnabled);

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  useEffect(() => {
    ttsRef.current = ttsEnabled;
  }, [ttsEnabled]);

  const speak = useCallback((text: string) => {
    if (!ttsRef.current || typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.04;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
  }, []);

  const attachEvents = useCallback(
    async (id: string) => {
      const { url } = await fetchEventsUrl({ data: { session_id: id } });
      const es = new EventSource(url);
      eventSourceRef.current = es;
      es.addEventListener("tip", (ev) => {
        const tip = JSON.parse((ev as MessageEvent).data) as LiveTip;
        setTips((current) =>
          current.some((t) => t.tip_id === tip.tip_id) ? current : [tip, ...current],
        );
        speak(tip.action_sentence);
      });
      es.addEventListener("end", () => {
        es.close();
      });
      es.onerror = () => {
        // EventSource reconnects automatically; keep this quiet unless the
        // session has already ended.
      };
    },
    [fetchEventsUrl, speak],
  );

  const sendDelta = useCallback(
    async (id: string, manual = false) => {
      const full = transcriptRef.current;
      const delta = manual
        ? full.slice(Math.max(0, full.length - 1600))
        : full.slice(sentOffsetRef.current);
      const clean = delta.trim();
      if (!clean || (!manual && clean.split(/\s+/).length < 5)) return;
      sentOffsetRef.current = full.length;
      await postChunk({ data: { session_id: id, text: clean, manual } });
    },
    [postChunk],
  );

  const start = useCallback(
    async (options: StartLiveOptions) => {
      setPhase("starting");
      setError(null);
      setTips([]);
      try {
        const session = await createSession({
          data: {
            precall_request_id: options.precallRequestId,
            pasted_context: options.pastedContext ?? "",
            spoken_setup: options.spokenSetup ?? "",
            precall_brief: options.precallBrief ?? "",
            precall_facts: options.precallFacts ?? "",
            max_tips: options.maxTips ?? 1,
            tts_enabled: options.ttsEnabled ?? false,
          },
        });
        setSessionId(session.session_id);
        sentOffsetRef.current = transcriptRef.current.length;
        await attachEvents(session.session_id);
        intervalRef.current = setInterval(() => {
          void sendDelta(session.session_id, false);
        }, 25_000);
        setPhase("listening");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Live session failed to start");
        setPhase("error");
      }
    },
    [attachEvents, createSession, sendDelta],
  );

  const requestTipNow = useCallback(async () => {
    if (!sessionId) return;
    try {
      await sendDelta(sessionId, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Manual tip failed");
    }
  }, [sendDelta, sessionId]);

  const stop = useCallback(async () => {
    setPhase("ending");
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = null;
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    if (sessionId) {
      await closeSession({ data: { session_id: sessionId } }).catch(() => null);
    }
    setSessionId(null);
    setPhase("idle");
  }, [closeSession, sessionId]);

  useEffect(
    () => () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      eventSourceRef.current?.close();
    },
    [],
  );

  return {
    phase,
    sessionId,
    tips,
    error,
    start,
    stop,
    requestTipNow,
    isLive: phase === "starting" || phase === "listening",
  };
}
