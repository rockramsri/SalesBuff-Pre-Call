import { useEffect, useRef, type RefObject } from "react";
import { Mic } from "lucide-react";

/**
 * Broad yellow bar shown only while recording. Draws a live spike-bar
 * waveform (voice-recorder style) from the shared mic analyser owned by the
 * speech-recorder hook — no separate mic stream.
 */
export function VoiceBar({ analyserRef }: { analyserRef: RefObject<AnalyserNode | null> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let raf = 0;
    const ink = "rgba(22, 20, 12, 0.92)";

    const drawBar = (
      ctx: CanvasRenderingContext2D,
      x: number,
      mid: number,
      barW: number,
      barH: number,
    ) => {
      const r = barW / 2;
      const y = mid - barH / 2;
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + barW, y, x + barW, y + barH, r);
      ctx.arcTo(x + barW, y + barH, x, y + barH, r);
      ctx.arcTo(x, y + barH, x, y, r);
      ctx.arcTo(x, y, x + barW, y, r);
      ctx.closePath();
      ctx.fill();
    };

    const draw = () => {
      raf = requestAnimationFrame(draw);
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const cssW = canvas.clientWidth;
      const cssH = canvas.clientHeight;
      if (canvas.width !== cssW * dpr || canvas.height !== cssH * dpr) {
        canvas.width = cssW * dpr;
        canvas.height = cssH * dpr;
      }
      const w = canvas.width;
      const h = canvas.height;
      const mid = h / 2;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = ink;

      const bars = Math.max(24, Math.floor(w / (7 * dpr)));
      const slot = w / bars;
      const barW = Math.max(2 * dpr, slot * 0.45);
      const minH = 3 * dpr;

      const analyser = analyserRef.current;
      if (!analyser) {
        for (let i = 0; i < bars; i++) {
          drawBar(ctx, i * slot + (slot - barW) / 2, mid, barW, minH);
        }
        return;
      }

      const buf = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(buf);

      // One spike per bar: RMS amplitude of a chunk of the waveform, mirrored
      // around the center line (voice-recorder look).
      const chunk = Math.floor(buf.length / bars) || 1;
      for (let i = 0; i < bars; i++) {
        let sum = 0;
        const start = i * chunk;
        for (let j = 0; j < chunk; j++) {
          const v = (buf[start + j] - 128) / 128; // -1..1
          sum += v * v;
        }
        const rms = Math.sqrt(sum / chunk); // 0..1
        const barH = Math.min(h, Math.max(minH, rms * h * 2.4));
        drawBar(ctx, i * slot + (slot - barW) / 2, mid, barW, barH);
      }
    };

    draw();
    return () => {
      if (raf) cancelAnimationFrame(raf);
    };
  }, [analyserRef]);

  return (
    <div className="voice-bar mt-4 animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="voice-bar-label">
        <span className="voice-dot" />
        <Mic size={15} />
        <span>Listening…</span>
      </div>
      <canvas ref={canvasRef} className="voice-canvas" />
    </div>
  );
}
