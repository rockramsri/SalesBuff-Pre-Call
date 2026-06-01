import { useState } from "react";
import { ChevronDown, BookOpen, MessageSquareQuote } from "lucide-react";
import type { BriefCard as BriefCardType } from "@/lib/api/research.functions";
import {
  ActionTypePill,
  CategoryPill,
  PriorityPill,
  UseWhenPill,
} from "./Pills";
import { CitationsPanel } from "./CitationsPanel";

export function BriefCard({ card }: { card: BriefCardType }) {
  const [expanded, setExpanded] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const hasCitations = card.citations && card.citations.length > 0;

  const onClick = () => {
    if (!expanded) setExpanded(true);
    else if (hasCitations) setShowSources((s) => !s);
  };

  return (
    <article
      className="skeuo-card p-5 cursor-pointer text-left"
      data-expanded={expanded}
      onClick={onClick}
    >
      <header className="flex items-center justify-between gap-2 mb-3">
        <CategoryPill value={card.category} />
        <ChevronDown
          size={18}
          className={`text-[var(--salesbuff-ink-soft)] transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </header>

      <h3 className="font-display text-lg font-bold leading-tight text-[var(--salesbuff-ink)] mb-1.5">
        {card.title}
      </h3>
      <p className="text-[0.95rem] text-[var(--salesbuff-ink)] leading-snug">{card.preview}</p>

      <div className="flex flex-wrap gap-1.5 mt-3">
        <ActionTypePill value={card.action_type} />
        <UseWhenPill value={card.use_when} />
        <PriorityPill value={card.priority} />
      </div>

      {card.talk_track && (
        <div className="mt-3 flex gap-2 items-start rounded-md bg-[oklch(0.96_0.03_95)] border border-[oklch(0.82_0.06_85)] px-3 py-2">
          <MessageSquareQuote size={15} className="mt-0.5 shrink-0 text-[var(--salesbuff-ink-soft)]" />
          <p className="text-[0.9rem] italic leading-snug text-[var(--salesbuff-ink)]">
            “{card.talk_track}”
          </p>
        </div>
      )}

      {expanded && (card.detail || hasCitations) && (
        <div className="mt-4 pt-4 border-t border-dashed border-[oklch(0.7_0.05_75/0.6)]">
          {card.detail && (
            <p className="text-[0.95rem] leading-relaxed text-[var(--salesbuff-ink)]">{card.detail}</p>
          )}

          {hasCitations && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setShowSources((s) => !s); }}
              className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[var(--salesbuff-ink-soft)] hover:text-[var(--salesbuff-ink)]"
            >
              <BookOpen size={13} />
              {showSources ? "Hide" : "Show"} sources ({card.citations.length})
            </button>
          )}

          {showSources && <CitationsPanel citations={card.citations} />}
        </div>
      )}
    </article>
  );
}
