import { useMemo } from "react";
import type { SalesBrief, CardCategory } from "@/lib/api/research.functions";
import { BriefCard } from "./BriefCard";
import { PRIORITY_RANK } from "./Pills";

// The report's conversation-flow grouping: each call section holds a set of
// move categories, rendered in call order.
const FLOW_SECTIONS: { title: string; categories: CardCategory[] }[] = [
  { title: "Open", categories: ["opening_move", "rapport_hook"] },
  { title: "Diagnose", categories: ["priority_signal", "pain_hypothesis", "stakeholder_hint"] },
  { title: "Differentiate", categories: ["differentiation_angle", "proof_point", "objection_prep"] },
  { title: "Advance", categories: ["next_step"] },
  { title: "Watch-outs", categories: ["watch_out", "open_question"] },
];

const SECTION_OF = new Map<CardCategory, string>(
  FLOW_SECTIONS.flatMap((s) => s.categories.map((c) => [c, s.title] as const)),
);

export function CardList({ brief }: { brief: SalesBrief }) {
  const groups = useMemo(() => {
    const m = new Map<string, SalesBrief["cards"]>();
    for (const card of brief.cards) {
      const section = SECTION_OF.get(card.category) ?? "Watch-outs";
      if (!m.has(section)) m.set(section, []);
      m.get(section)!.push(card);
    }
    for (const cards of m.values()) {
      cards.sort((a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]);
    }
    return FLOW_SECTIONS.filter((s) => m.has(s.title)).map((s) => ({
      title: s.title,
      items: m.get(s.title)!,
    }));
  }, [brief]);

  return (
    <div className="space-y-8">
      {groups.map((g) => (
        <section key={g.title}>
          <h2 className="font-display text-sm uppercase tracking-[0.2em] font-bold text-[oklch(0.78_0.08_85)] mb-3 flex items-center gap-3">
            <span className="h-px flex-none w-6 bg-[oklch(0.55_0.1_70)]" />
            {g.title}
            <span className="text-[var(--salesbuff-ink-soft)] font-normal normal-case tracking-normal text-xs">
              {g.items.length} {g.items.length === 1 ? "card" : "cards"}
            </span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {g.items.map((card) => (
              <BriefCard key={card.card_id} card={card} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
