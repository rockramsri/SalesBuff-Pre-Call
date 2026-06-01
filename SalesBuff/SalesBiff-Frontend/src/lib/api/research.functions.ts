// Server functions that proxy to the SalesBuff Python due-diligence API.
// The browser only talks to these server functions; they call the backend
// server-side, so no CORS and the backend URL/keys stay off the client.
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

export type Priority = "high" | "medium" | "low";
export type Confidence = "high" | "medium" | "low";

// Conversation-move taxonomy for the Actions tab.
export type CardCategory =
  | "opening_move"
  | "rapport_hook"
  | "priority_signal"
  | "pain_hypothesis"
  | "differentiation_angle"
  | "proof_point"
  | "stakeholder_hint"
  | "objection_prep"
  | "next_step"
  | "watch_out"
  | "open_question";

export type ActionType = "say" | "ask" | "show" | "avoid" | "verify";
export type UseWhen =
  | "opening"
  | "discovery"
  | "differentiation"
  | "objection"
  | "close"
  | "follow_up";

export interface Citation {
  source: "web" | "court_listener";
  url: string;
  title: string;
  quote: string;
}
export interface BriefCard {
  card_id: string;
  category: CardCategory;
  action_type: ActionType;
  use_when: UseWhen;
  title: string;
  preview: string;
  talk_track: string;
  detail: string;
  priority: Priority;
  confidence: Confidence;
  citations: Citation[];
}
export interface SalesBrief {
  subject: { prospect: string; contact: string; incumbent?: string | null };
  opening_line: string;
  next_step_line: string;
  cards: BriefCard[];
  generated_at: string;
}

// FACTS tab: evidence dossier grouped into sections.
export interface FactFinding {
  category: string;
  headline: string;
  detail: string;
  why_it_matters: string;
  citations: Citation[];
}
export interface FactSection {
  category: string;
  display: string;
  findings: FactFinding[];
}
export interface FactsReport {
  subject: { prospect: string; contact: string; incumbent?: string | null };
  sections: FactSection[];
  generated_at: string;
}

export type ResearchStatus =
  | { status: "pending"; stage: string; progress: number }
  | {
      status: "completed";
      brief: SalesBrief | null;
      facts: FactsReport | null;
      warnings: string[];
    }
  | { status: "failed"; error: string }
  | { status: "not_found" };

function backendUrl(): string {
  return (
    process.env.SALESBUFF_API_URL ||
    process.env.RELLA_API_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

export interface Usage {
  used: number;
  limit: number;
  remaining: number;
}

export const submitResearch = createServerFn({ method: "POST" })
  .inputValidator(
    z.object({
      prompt: z.string().min(1).max(8000),
      keys: z
        .object({
          openai: z.string().optional(),
          tavily: z.string().optional(),
          courtlistener: z.string().optional(),
        })
        .optional(),
    }),
  )
  .handler(async ({ data }): Promise<{ request_id: string; usage?: Usage }> => {
    const body: Record<string, unknown> = { prompt: data.prompt };
    if (data.keys) body.keys = data.keys;
    const res = await fetch(`${backendUrl()}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.status === 429) {
      const body = (await res.json().catch(() => null)) as {
        detail?: { message?: string };
      } | null;
      throw new Error(
        body?.detail?.message ?? "Usage limit reached for due-diligence runs.",
      );
    }
    if (!res.ok) {
      throw new Error(`Backend submit failed (${res.status})`);
    }
    const json = (await res.json()) as { request_id: string; usage?: Usage };
    return { request_id: json.request_id, usage: json.usage };
  });

export const getUsage = createServerFn({ method: "GET" }).handler(
  async (): Promise<Usage> => {
    const res = await fetch(`${backendUrl()}/usage`);
    if (!res.ok) throw new Error(`Backend usage failed (${res.status})`);
    return (await res.json()) as Usage;
  },
);

export const getResearch = createServerFn({ method: "POST" })
  .inputValidator(z.object({ id: z.string().min(1) }))
  .handler(async ({ data }): Promise<ResearchStatus> => {
    const res = await fetch(`${backendUrl()}/research/${encodeURIComponent(data.id)}`);
    if (res.status === 404) return { status: "not_found" };
    if (!res.ok) throw new Error(`Backend poll failed (${res.status})`);

    const json = (await res.json()) as {
      status: string;
      stage?: string;
      progress?: number;
      brief?: SalesBrief | null;
      facts?: FactsReport | null;
      warnings?: string[];
      error?: string | null;
    };

    if (json.status === "completed") {
      return {
        status: "completed",
        brief: json.brief ?? null,
        facts: json.facts ?? null,
        warnings: json.warnings ?? [],
      };
    }
    if (json.status === "failed") {
      return { status: "failed", error: json.error ?? "Research failed" };
    }
    if (json.status === "not_found") {
      return { status: "not_found" };
    }
    return { status: "pending", stage: json.stage ?? "queued", progress: json.progress ?? 0 };
  });
