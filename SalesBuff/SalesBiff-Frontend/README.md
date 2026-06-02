<!-- 🟡 SalesBuff frontend -->

# 🟡 SalesBuff — Frontend (TanStack Start)

The web app where a sales rep speaks or types an account scenario, runs the
brief, and reads the result as two tabs: **Actions** (coaching moves) and
**Facts** (evidence dossier).

Stack: **TanStack Start** (SSR + server functions) · **Vite** · **React 19** ·
**Tailwind v4** · **Nitro** (deploy). UI is a flat, high-contrast yellow/ink
"index-card" theme.

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
| `SALESBUFF_API_URL` | `http://127.0.0.1:8000` | Backend base URL (used **server-side** only) |
| `NITRO_PRESET` | `vercel` | Deploy target preset (set automatically in `vite.config.ts`) |

> The browser never calls the backend directly. TanStack **server functions**
> (`src/lib/api/research.functions.ts`) proxy to it, so the backend URL stays
> server-side and there's no CORS to manage.

---

## Scripts

| Command | Does |
|---------|------|
| `npm run dev` | Local dev server (HMR) |
| `npm run build` | Production build (Nitro → `.vercel/output`) |
| `npm run preview` | Preview a production build |
| `npm run lint` | ESLint |
| `npm run format` | Prettier |

---

## How it works

1. `useSpeechRecorder` captures voice (Web Speech API) and shows a live waveform
   bar while you talk; you can edit the transcript before running.
2. **Run** calls `submitResearch` → backend returns a `request_id`.
3. The app polls `getResearch` every second, showing stage + progress, until the
   brief is ready.
4. Results render as **Actions** (`CardList` / `BriefCard`) and **Facts**
   (`FactsView`), with collapsible cards and grounded source links.

Key files:

```
src/
├── routes/
│   ├── __root.tsx          # shell, error/404 boundaries, meta
│   └── index.tsx           # the whole app screen
├── components/salesbuff/   # BriefCard, CardList, FactsView, CitationsPanel,
│                           # VoiceBar, RecordButton, Pills, RichText
├── hooks/use-speech-recorder.ts
└── lib/api/research.functions.ts   # server functions → backend
```

`src/components/ui/` is the shadcn-style primitive library (not all of it is used).

---

## Deploy (Vercel)

- **Root Directory:** `SalesBuff/SalesBiff-Frontend`
- **Framework Preset:** Other (a `vercel.json` is included: `framework: null`,
  `outputDirectory: .vercel/output`)
- **Env:** `SALESBUFF_API_URL` = your Render backend URL (no trailing slash)

`vite.config.ts` already forces the Nitro **`vercel`** preset and the
`.vercel/output` Build Output layout, so `npm run build` produces exactly what
Vercel expects.

> ⚠️ This is a TanStack Start **SSR** app — every route needs the server
> function. Don't deploy it as a static site (that 404s every route).
