import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

function backendUrl(): string {
  return (process.env.SALESBUFF_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

export type TipConfidence = "high" | "medium" | "low";
export type TipSource = "immediate" | "background";

export interface LiveTip {
  tip_id: string;
  action_sentence: string;
  reason: string;
  trigger: string;
  confidence: TipConfidence;
  source: TipSource;
  stage?: string;
  tip_type?: string;
  created_at: string;
}

export interface LiveSessionState {
  session_id: string;
  expires_at: string;
  ended: boolean;
  tips: LiveTip[];
}

export const createLiveSession = createServerFn({ method: "POST" })
  .inputValidator(
    z.object({
      precall_request_id: z.string().optional(),
      pasted_context: z.string().max(12000).optional(),
      spoken_setup: z.string().max(4000).optional(),
      precall_brief: z.string().max(30000).optional(),
      precall_facts: z.string().max(30000).optional(),
      max_tips: z.number().min(1).max(3).optional(),
      tts_enabled: z.boolean().optional(),
    }),
  )
  .handler(async ({ data }): Promise<{ session_id: string; expires_at: string }> => {
    const res = await fetch(`${backendUrl()}/onfly/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Live session create failed (${res.status})`);
    return (await res.json()) as { session_id: string; expires_at: string };
  });

export const sendLiveChunk = createServerFn({ method: "POST" })
  .inputValidator(
    z.object({
      session_id: z.string().min(1),
      text: z.string().min(1).max(6000),
      manual: z.boolean().optional(),
    }),
  )
  .handler(async ({ data }): Promise<{ status: string; tip_count: number }> => {
    const res = await fetch(
      `${backendUrl()}/onfly/sessions/${encodeURIComponent(data.session_id)}/chunks`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: data.text, manual: data.manual ?? false }),
      },
    );
    if (!res.ok) throw new Error(`Live chunk failed (${res.status})`);
    return (await res.json()) as { status: string; tip_count: number };
  });

export const getLiveSession = createServerFn({ method: "POST" })
  .inputValidator(z.object({ session_id: z.string().min(1) }))
  .handler(async ({ data }): Promise<LiveSessionState> => {
    const res = await fetch(
      `${backendUrl()}/onfly/sessions/${encodeURIComponent(data.session_id)}`,
    );
    if (!res.ok) throw new Error(`Live session fetch failed (${res.status})`);
    return (await res.json()) as LiveSessionState;
  });

export const endLiveSession = createServerFn({ method: "POST" })
  .inputValidator(z.object({ session_id: z.string().min(1) }))
  .handler(async ({ data }): Promise<{ ended: boolean }> => {
    const res = await fetch(
      `${backendUrl()}/onfly/sessions/${encodeURIComponent(data.session_id)}`,
      {
        method: "DELETE",
      },
    );
    if (!res.ok) throw new Error(`Live session end failed (${res.status})`);
    return (await res.json()) as { ended: boolean };
  });

export const getLiveEventsUrl = createServerFn({ method: "POST" })
  .inputValidator(z.object({ session_id: z.string().min(1) }))
  .handler(
    async ({ data }): Promise<{ url: string }> => ({
      url: `${backendUrl()}/onfly/sessions/${encodeURIComponent(data.session_id)}/events`,
    }),
  );
