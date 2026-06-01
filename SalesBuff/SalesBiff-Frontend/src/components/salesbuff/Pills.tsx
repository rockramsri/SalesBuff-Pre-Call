import {
  type ActionType,
  type CardCategory,
  type Confidence,
  type Priority,
  type UseWhen,
} from "@/lib/api/research.functions";

export const CATEGORY_LABEL: Record<CardCategory, string> = {
  opening_move: "Opening move",
  rapport_hook: "Rapport hook",
  priority_signal: "Priority signal",
  pain_hypothesis: "Pain hypothesis",
  differentiation_angle: "Differentiation",
  proof_point: "Proof point",
  stakeholder_hint: "Stakeholder",
  objection_prep: "Objection prep",
  next_step: "Next step",
  watch_out: "Watch out",
  open_question: "Open question",
};

const ACTION_LABEL: Record<ActionType, string> = {
  say: "Say",
  ask: "Ask",
  show: "Show",
  avoid: "Avoid",
  verify: "Verify",
};

const USE_WHEN_LABEL: Record<UseWhen, string> = {
  opening: "Opening",
  discovery: "Discovery",
  differentiation: "Differentiation",
  objection: "Objection",
  close: "Close",
  follow_up: "Follow-up",
};

export const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 };

export function PriorityPill({ value }: { value: Priority }) {
  return <span className={`pill pill-priority-${value}`}>{value} priority</span>;
}
export function ConfidencePill({ value }: { value: Confidence }) {
  return <span className="pill pill-confidence">{value} confidence</span>;
}
export function CategoryPill({ value }: { value: CardCategory }) {
  return <span className="pill pill-category">{CATEGORY_LABEL[value]}</span>;
}
export function ActionTypePill({ value }: { value: ActionType }) {
  return <span className="pill pill-confidence">{ACTION_LABEL[value]}</span>;
}
export function UseWhenPill({ value }: { value: UseWhen }) {
  return <span className="pill pill-confidence">{USE_WHEN_LABEL[value]}</span>;
}
