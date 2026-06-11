import { useState } from "react";
import { ChevronDown, BookOpen, MessageSquareQuote } from "lucide-react";
import type { BriefCard as BriefCardType } from "@/lib/api/research.functions";
import { ActionTypePill, CategoryPill, PriorityPill, UseWhenPill } from "./Pills";
import { CitationsPanel } from "./CitationsPanel";
import { Linkified } from "./RichText";

export function BriefCard({ card }: { card: BriefCardType }) {
  const [expanded, setExpanded] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const hasCitations = card.citations && card.citations.length > 0;
  const hasMore = Boolean(card.detail || hasCitations);

  // Whole card toggles open/closed; sources have their own button below.
  const toggle = () => {
    setExpanded((e) => {
      if (e) setShowSources(false);
      return !e;
    });
  };

  return (
    <article
      className="skeuo-card p-5 cursor-pointer text-left"
      data-expanded={expanded}
      onClick={toggle}
    >
      <header className="flex items-center justify-between gap-2 mb-3">
        <CategoryPill value={card.category} />
        {hasMore && (
          <ChevronDown
            size={18}
            aria-label={expanded ? "Collapse" : "Expand"}
            className={`text-[var(--salesbuff-ink-soft)] transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        )}
      </header>

      <h3 className="result-card-title text-[1.05rem] font-semibold leading-snug text-[var(--salesbuff-ink)] mb-1.5">
        {card.title}
      </h3>
      <p className="result-card-body text-[0.95rem] text-[var(--salesbuff-ink)] leading-snug">
        <Linkified text={card.preview} />
      </p>

      <div className="flex flex-wrap gap-1.5 mt-3">
        <ActionTypePill value={card.action_type} />
        <UseWhenPill value={card.use_when} />
        <PriorityPill value={card.priority} />
      </div>

      {card.talk_track && (
        <div className="mt-3 flex gap-2 items-start rounded-md talk-track bg-[var(--sb-quote-bg)] border border-[var(--sb-quote-border)] px-3 py-2">
          <MessageSquareQuote
            size={15}
            className="mt-0.5 shrink-0 text-[var(--salesbuff-ink-soft)]"
          />
          <p className="text-[0.9rem] italic leading-snug text-[var(--salesbuff-ink)]">
            “{card.talk_track}”
          </p>
        </div>
      )}

      {expanded && (card.detail || hasCitations) && (
        <div className="mt-4 pt-4 border-t border-dashed border-[var(--sb-dashed)]">
          {card.detail && (
            <p className="text-[0.95rem] leading-relaxed text-[var(--salesbuff-ink)]">
              <Linkified text={card.detail} />
            </p>
          )}

          {hasCitations && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowSources((s) => !s);
              }}
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
