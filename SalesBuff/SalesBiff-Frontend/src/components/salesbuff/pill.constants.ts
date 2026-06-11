import type { CardCategory, Priority } from "@/lib/api/research.functions";

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

export const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
