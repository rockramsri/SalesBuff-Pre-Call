import type { ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import type { Citation } from "@/lib/api/research.functions";

const URL_RE = /(https?:\/\/[^\s)]+)/g;

/** A short, human-friendly label for a URL (its host, sans "www."). */
export function hostLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** What to show for a citation: its title, else a crisp host label. */
export function citationLabel(c: Citation): string {
  const title = (c.title ?? "").trim();
  return title || hostLabel(c.url);
}

/**
 * Renders text, replacing any raw URL with a crisp host-labelled link.
 * Link clicks stop propagation so they don't toggle a parent card.
 */
export function Linkified({ text }: { text: string }): ReactNode {
  if (!text) return null;
  const nodes: ReactNode[] = [];
  const re = new RegExp(URL_RE);
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(<span key={key++}>{text.slice(last, m.index)}</span>);
    const url = m[0];
    nodes.push(
      <a
        key={key++}
        href={url}
        target="_blank"
        rel="noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex items-baseline gap-0.5 font-semibold text-[var(--salesbuff-ink)] underline decoration-[oklch(0.7_0.05_75)] underline-offset-2 hover:decoration-[var(--salesbuff-ink)]"
      >
        {hostLabel(url)}
        <ExternalLink size={11} className="shrink-0 self-center" />
      </a>,
    );
    last = m.index + url.length;
  }
  if (last < text.length) nodes.push(<span key={key++}>{text.slice(last)}</span>);
  return <>{nodes}</>;
}
