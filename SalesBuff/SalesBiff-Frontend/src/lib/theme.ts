// Multi-brand theming. One codebase, one Vercel project per skin — each sets
// VITE_THEME at build time. Vite statically replaces `import.meta.env.VITE_THEME`
// so the value is baked into the bundle (no runtime flicker, no client fetch).
//
//   VITE_THEME=sunrise   -> yellow flat skeuomorphic stage (SalesBuff default)
//   VITE_THEME=prism     -> orange→violet gradient, frosted glass
//   VITE_THEME=horizon   -> navy→white gradient, dark glass
//   VITE_THEME=folio     -> white editorial, royal purple accent
//   VITE_THEME=ember     -> warm cream page, brown recording theater

export type ThemeId = "sunrise" | "prism" | "horizon" | "folio" | "ember";

const THEME_IDS: readonly ThemeId[] = ["sunrise", "prism", "horizon", "folio", "ember"];

function normalizeTheme(value: string | undefined): ThemeId {
  const candidate = (value ?? "").trim().toLowerCase();
  return THEME_IDS.includes(candidate as ThemeId) ? (candidate as ThemeId) : "sunrise";
}

export const ACTIVE_THEME: ThemeId = normalizeTheme(import.meta.env.VITE_THEME);
