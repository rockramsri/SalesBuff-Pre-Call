import { useState } from "react";
import { ChevronDown, BookOpen } from "lucide-react";
import type { FactFinding, FactsReport } from "@/lib/api/research.functions";
import { CitationsPanel } from "./CitationsPanel";

export function FactsView({ facts }: { facts: FactsReport }) {
  if (facts.sections.length === 0) {
    return (
      <div className="skeuo-panel p-8 text-center text-muted-foreground">
        No verified facts surfaced for this account yet.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {facts.sections.map((section) => (
        <section key={section.category}>
          <h2 className="font-display text-sm uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)] mb-3 flex items-center gap-3">
            <span className="h-px flex-none w-6 bg-[oklch(0.55_0.1_70)]" />
            {section.display}
            <span className="text-[var(--salesbuff-ink-soft)] font-normal normal-case tracking-normal text-xs">
              {section.findings.length} {section.findings.length === 1 ? "fact" : "facts"}
            </span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {section.findings.map((f, i) => (
              <FactCard key={i} finding={f} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function FactCard({ finding }: { finding: FactFinding }) {
  const [expanded, setExpanded] = useState(false);
  const hasCitations = finding.citations && finding.citations.length > 0;
  const hasMore = Boolean(finding.detail || finding.why_it_matters || hasCitations);

  return (
    <article
      className="skeuo-card p-5 cursor-pointer text-left"
      data-expanded={expanded}
      onClick={() => hasMore && setExpanded((e) => !e)}
    >
      <header className="flex items-start justify-between gap-2">
        <h3 className="font-display text-base font-bold leading-tight text-[var(--salesbuff-ink)]">
          {finding.headline}
        </h3>
        {hasMore && (
          <ChevronDown
            size={18}
            className={`shrink-0 text-[var(--salesbuff-ink-soft)] transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        )}
      </header>

      {finding.why_it_matters && (
        <p className="text-[0.85rem] text-[var(--salesbuff-ink-soft)] leading-snug mt-1.5">
          {finding.why_it_matters}
        </p>
      )}

      {expanded && (
        <div className="mt-4 pt-4 border-t border-dashed border-[oklch(0.7_0.05_75/0.6)]">
          {finding.detail && (
            <p className="text-[0.95rem] leading-relaxed text-[var(--salesbuff-ink)]">
              {finding.detail}
            </p>
          )}
          {hasCitations && (
            <div className="mt-2 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[var(--salesbuff-ink-soft)]">
              <BookOpen size={13} /> {finding.citations.length}{" "}
              {finding.citations.length === 1 ? "source" : "sources"}
            </div>
          )}
          {hasCitations && <CitationsPanel citations={finding.citations} />}
        </div>
      )}
    </article>
  );
}
