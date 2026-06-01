import { useCallback, useEffect, useRef, useState } from "react";

// Minimal Web Speech API typings
interface SRResult { 0: { transcript: string }; isFinal: boolean }
interface SREvent { resultIndex: number; results: { length: number; [i: number]: SRResult } }
interface SRInstance {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: SREvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void; stop: () => void;
}
type SRCtor = new () => SRInstance;

export function useSpeechRecorder() {
  const [supported, setSupported] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SRInstance | null>(null);
  const finalRef = useRef("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    setSupported(Boolean(Ctor));
  }, []);

  const start = useCallback(() => {
    setError(null);
    const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) { setError("Voice capture not supported in this browser. Type your scenario."); return; }
    finalRef.current = "";
    const rec = new Ctor();
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalRef.current += r[0].transcript + " ";
        else interim += r[0].transcript;
      }
      setTranscript((finalRef.current + interim).trim());
    };
    rec.onerror = (ev) => setError(ev.error || "Voice error");
    rec.onend = () => setRecording(false);
    recRef.current = rec;
    try { rec.start(); setRecording(true); } catch (e) { setError(String(e)); }
  }, []);

  const stop = useCallback(() => {
    try { recRef.current?.stop(); } catch { /* noop */ }
    setRecording(false);
  }, []);

  return { supported, recording, transcript, setTranscript, start, stop, error };
}
