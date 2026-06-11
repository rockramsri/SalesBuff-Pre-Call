import type { Citation } from "@/lib/api/research.functions";

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
