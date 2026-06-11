<!-- SalesBuff frontend -->

# SalesBuff — Frontend (TanStack Start)

The web app where a sales rep prepares for and runs sales conversations in two
modes:

| Mode | What it does |
|------|--------------|
| **Pre-call** | Speak or type an account scenario → run due diligence → read **Actions** (coaching moves) and **Facts** (evidence dossier). |
| **On-fly** | Start a live coaching session → speak during the call → receive real-time **coaching tips** as cards stream in. |

Stack: **TanStack Start** (SSR + server functions) · **Vite** · **React 19** ·
**Tailwind v4** · **Nitro** (deploy). UI uses configurable build-time themes
(see below).

---

## UI themes (`VITE_THEME`)

One repo, multiple deploy skins. Set `VITE_THEME` at build time (Vercel env var
or `.env.local`). Unknown values fall back to **sunrise**.

| Theme | Look | npm dev script |
|-------|------|----------------|
| **sunrise** (default) | Yellow flat skeuomorphic stage, black ink | `npm run dev:sunrise` |
| **prism** | Orange→violet gradient, frosted glass | `npm run dev:prism` |
| **horizon** | Navy→white gradient, dark glass cards | `npm run dev:horizon` |
| **folio** | White editorial, purple accent, serif headlines | `npm run dev:folio` |
| **ember** | Warm cream page, brown recording theater, orange-red accent | `npm run dev:ember` |

Build per theme: `npm run build:prism`, etc. Each Vercel project sets its own
`VITE_THEME`.

---

## Setup (local)

```bash
cd SalesBuff/SalesBiff-Frontend
npm install
npm run dev
```

By default it talks to the backend at `http://127.0.0.1:8000`. To point elsewhere,
copy the env template:

```bash
cp .env.example .env        # then set SALESBUFF_API_URL
```

| Var | Default | Purpose |
|-----|---------|---------|
| `VITE_THEME` | `sunrise` | UI skin (baked in at build time) |
| `SALESBUFF_API_URL` | `http://127.0.0.1:8000` | Backend base URL (used **server-side** only) |
| `NITRO_PRESET` | `vercel` | Deploy target preset (set automatically in `vite.config.ts`) |

> The browser never calls the backend directly. TanStack **server functions**
> in `src/lib/api/` proxy to it, so the backend URL stays server-side and
> there's no CORS to manage.

---

## Scripts

| Command | Does |
|---------|------|
| `npm run dev` | Local dev server (HMR), sunrise theme |
| `npm run dev:<theme>` | Dev with a specific theme (prism, horizon, …) |
| `npm run build` | Production build (Nitro → `.vercel/output`) |
| `npm run build:<theme>` | Production build with a specific theme |
| `npm run preview` | Preview a production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript (`tsc --noEmit`) |
| `npm run format` | Prettier |

---

## How it works

### Pre-call mode

1. `useSpeechRecorder` captures voice (Web Speech API) and shows a live waveform
   bar while you talk; you can edit the transcript before running.
2. **Run due diligence** calls `submitResearch` → backend returns a `request_id`.
3. The app polls `getResearch` every second, showing stage + progress, until the
   brief is ready.
4. Results render as **Actions** (`CardList` / `BriefCard`) and **Facts**
   (`FactsView`), with collapsible cards and grounded source links.

Pre-call and On-fly keep **separate transcript state** — completing a pre-call
run does not overwrite the On-fly transcript box (and vice versa).

### On-fly mode

1. Switch to **On-fly** in the header. Optionally attach a completed pre-call
   brief (checkmark only — content stays in the pre-call transcript).
2. Fill **context** (pasted notes, call goal) in the setup panel; grant mic
   consent. The setup panel collapses once a session starts.
3. **Start coaching** creates a live session (`createLiveSession`) with optional
   pre-call brief/facts sent directly to the backend.
4. `useSpeechRecorder` streams transcript chunks; `useLiveCoaching` sends them
   to `/onfly/sessions/{id}/chunks` and listens on SSE for new tips.
5. Tips appear as **LiveTipCard** components (stage + tip type labels). The
   floating **Get tip now** button requests a manual tip without stopping the mic.
6. **End session** closes the SSE stream and triggers backend session logging.

Key files:

```
src/
├── routes/
│   ├── __root.tsx              # shell, error/404 boundaries, meta
│   └── index.tsx               # mode switch, pre-call + on-fly UI
├── components/salesbuff/       # BriefCard, CardList, FactsView, VoiceBar,
│                               # RecordButton, Pills, RichText, BrandMark
├── hooks/
│   ├── use-speech-recorder.ts  # Web Speech API + waveform (shared by both modes)
│   └── use-live-coaching.ts    # session lifecycle, chunk ingest, SSE tips
├── lib/
│   ├── theme.ts                # VITE_THEME → data-theme on <html>
│   └── api/
│       ├── research.functions.ts
│       └── onfly.functions.ts
└── styles.css                  # theme tokens + per-theme overrides
```

---

## Deploy (Vercel)

- **Root Directory:** `SalesBuff/SalesBiff-Frontend`
- **Framework Preset:** Other (a `vercel.json` is included: `framework: null`,
  `outputDirectory: .vercel/output`)
- **Env:** `SALESBUFF_API_URL` = your Render backend URL (no trailing slash)
- **Env:** `VITE_THEME` = one of `sunrise`, `prism`, `horizon`, `folio`, `ember`

`vite.config.ts` already forces the Nitro **`vercel`** preset and the
`.vercel/output` Build Output layout, so `npm run build` produces exactly what
Vercel expects.

> ⚠️ This is a TanStack Start **SSR** app — every route needs the server
> function. Don't deploy it as a static site (that 404s every route).

On-fly requires a backend with `/onfly/*` routes (included when you run
`salesbuff.api:app`). Mic access needs **HTTPS** in production (Vercel provides this).
