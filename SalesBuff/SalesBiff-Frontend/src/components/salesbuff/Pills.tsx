import {
  type ActionType,
  type CardCategory,
  type Priority,
  type UseWhen,
} from "@/lib/api/research.functions";

import { CATEGORY_LABEL } from "./pill.constants";

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

export function PriorityPill({ value }: { value: Priority }) {
  return <span className={`pill pill-priority-${value}`}>{value} priority</span>;
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
