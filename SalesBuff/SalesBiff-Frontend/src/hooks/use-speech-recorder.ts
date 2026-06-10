import { useCallback, useEffect, useRef, useState } from "react";

// Minimal Web Speech API typings
interface SRResult {
  0: { transcript: string };
  isFinal: boolean;
}
interface SREvent {
  resultIndex: number;
  results: { length: number; [i: number]: SRResult };
}
interface SRInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type SRCtor = new () => SRInstance;

function getSpeechCtor(): SRCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

function joinSpeech(...parts: string[]): string {
  return parts
    .map((p) => p.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ");
}

export function useSpeechRecorder() {
  const [supported, setSupported] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SRInstance | null>(null);
  // Text layers: base = whatever was in the box when recording started (typed
  // or from a previous take); final = speech committed by the recognizer;
  // interim = words still being recognized. The box always shows all three, so
  // silence restarts or re-recording never erase earlier content.
  const baseRef = useRef("");
  const finalRef = useRef("");
  const interimRef = useRef("");
  const transcriptRef = useRef("");
  // User intent — keep listening until they explicitly stop (Chrome ends
  // recognition after silence even with continuous=true).
  const wantsRecordingRef = useRef(false);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const meterActiveRef = useRef(false);

  useEffect(() => {
    setSupported(Boolean(getSpeechCtor()));
  }, []);

  const teardownMeter = useCallback(() => {
    meterActiveRef.current = false;
    analyserRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      void audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
  }, []);

  const setupMeter = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return;
    if (streamRef.current) return;
    meterActiveRef.current = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!meterActiveRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;
      const Ctx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.6;
      source.connect(analyser);
      analyserRef.current = analyser;
    } catch {
      /* mic blocked — waveform just stays flat */
    }
  }, []);

  const attachRecognizer = useCallback(
    (rec: SRInstance) => {
      rec.lang = "en-US";
      rec.continuous = true;
      rec.interimResults = true;
      rec.onresult = (e) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          if (r.isFinal) finalRef.current = joinSpeech(finalRef.current, r[0].transcript);
          else interim += r[0].transcript;
        }
        interimRef.current = interim;
        setTranscript(joinSpeech(baseRef.current, finalRef.current, interim));
      };
      rec.onerror = (ev) => {
        const code = ev.error || "Voice error";
        if (code === "not-allowed" || code === "service-not-allowed") {
          wantsRecordingRef.current = false;
          setError("Microphone permission denied.");
        } else if (code !== "no-speech" && code !== "aborted") {
          setError(code);
        }
      };
      rec.onend = () => {
        // Commit any words that were still interim when recognition cut out
        // (silence/TTS) so the restart never loses or rewinds text.
        if (interimRef.current) {
          finalRef.current = joinSpeech(finalRef.current, interimRef.current);
          interimRef.current = "";
        }
        if (!wantsRecordingRef.current) {
          setRecording(false);
          teardownMeter();
          return;
        }
        restartTimerRef.current = setTimeout(() => {
          if (!wantsRecordingRef.current) return;
          const Ctor = getSpeechCtor();
          if (!Ctor) return;
          try {
            const next = new Ctor();
            attachRecognizer(next);
            recRef.current = next;
            next.start();
          } catch {
            wantsRecordingRef.current = false;
            setRecording(false);
            teardownMeter();
          }
        }, 150);
      };
      recRef.current = rec;
    },
    [teardownMeter],
  );

  const start = useCallback(() => {
    const Ctor = getSpeechCtor();
    if (!Ctor) {
      setError("Voice capture not supported in this browser. Type your scenario.");
      return;
    }
    wantsRecordingRef.current = true;
    setError(null);
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    // Preserve whatever is already in the box (typed text or a previous take);
    // new speech appends after it instead of overwriting.
    baseRef.current = transcriptRef.current.trim();
    finalRef.current = "";
    interimRef.current = "";
    const rec = new Ctor();
    attachRecognizer(rec);
    try {
      rec.start();
      setRecording(true);
      void setupMeter();
    } catch (e) {
      wantsRecordingRef.current = false;
      setError(String(e));
    }
  }, [attachRecognizer, setupMeter]);

  const stop = useCallback(() => {
    wantsRecordingRef.current = false;
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    restartTimerRef.current = null;
    try {
      recRef.current?.stop();
    } catch {
      /* noop */
    }
    recRef.current = null;
    setRecording(false);
    teardownMeter();
  }, [teardownMeter]);

  useEffect(
    () => () => {
      wantsRecordingRef.current = false;
      if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
      teardownMeter();
    },
    [teardownMeter],
  );

  return { supported, recording, transcript, setTranscript, start, stop, error, analyserRef };
}
