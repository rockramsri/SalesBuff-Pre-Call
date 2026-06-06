import { ExternalLink, Gavel, Globe } from "lucide-react";
import type { Citation } from "@/lib/api/research.functions";
import { citationLabel, hostLabel } from "./RichText";

export function CitationsPanel({ citations }: { citations: Citation[] }) {
  if (!citations || citations.length === 0) return null;
  return (
    <div className="mt-4 pt-4 border-t border-dashed border-[oklch(0.7_0.05_75/0.6)]">
      <div className="text-[0.7rem] uppercase tracking-wider font-bold text-[var(--salesbuff-ink-soft)] mb-2">
        Sources
      </div>
      <ul className="space-y-2">
        {citations.map((c, i) => {
          const isLegal = c.source === "court_listener";
          const Icon = isLegal ? Gavel : Globe;
          const label = isLegal ? "Legal" : "Web";
          return (
            <li key={i} className="flex gap-2 items-start">
              <span className="mt-0.5 inline-flex items-center gap-1 text-[0.65rem] uppercase font-bold px-1.5 py-0.5 rounded bg-[oklch(0.88_0.05_85)] text-[var(--salesbuff-ink)] border border-[oklch(0.72_0.05_80)]">
                <Icon size={10} /> {label}
              </span>
              <div className="flex-1 min-w-0">
                <a
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  title={c.url}
                  className="inline-flex items-center gap-1 font-semibold text-[var(--salesbuff-ink)] hover:underline max-w-full"
                >
                  <span className="truncate">{citationLabel(c)}</span>
                  <ExternalLink size={12} className="shrink-0" />
                </a>
                {c.title?.trim() && (
                  <div className="text-[0.7rem] text-[var(--salesbuff-ink-soft)] truncate">
                    {hostLabel(c.url)}
                  </div>
                )}
                {c.quote && (
                  <p className="text-sm italic text-[var(--salesbuff-ink-soft)] mt-0.5">
                    “{c.quote}”
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
