<!-- 🟡 Contributing to SalesBuff -->

# 🟡 Contributing to SalesBuff

Thanks for helping improve SalesBuff. This guide covers local setup, the
conventions we follow, and how changes get pushed and redeployed.

---

## 1. Local setup

See the sub-READMEs for details:

- Backend → [`SalesBuff/README.md`](SalesBuff/README.md)
- Frontend → [`SalesBuff/SalesBiff-Frontend/README.md`](SalesBuff/SalesBiff-Frontend/README.md)

Short version (two terminals):

```bash
# Terminal 1 — backend
cd SalesBuff
pip install -r salesbuff/requirements.txt
cp salesbuff/.env.example salesbuff/.env   # add OPENAI_API_KEY + TAVILY_API_KEY
uvicorn salesbuff.api:app --port 8000 --reload

# Terminal 2 — frontend
cd SalesBuff/SalesBiff-Frontend
npm install
npm run dev
```

---

## 2. Project conventions

**Aim for simplicity and readability.** Small, focused functions; clear names;
comments only for non-obvious *why*, never to narrate the code.

### Python (backend)
- Keep the **ports/adapters** boundary: `research/` code depends on interfaces in
  `ports/`, never directly on a vendor SDK. New providers = new adapter.
- Prompts live in `domain/prompts.py` (pure strings). Editable sales logic lives
  in `domain_logic_sales/*.yaml` — change behavior there before touching code.
- The model never owns server metadata (ids, timestamps) — the server assigns it.
- Every shown card/finding must be **grounded** to a real source URL.

### TypeScript (frontend)
- The browser talks to the backend **only** through TanStack server functions in
  `src/lib/api/`. Don't fetch the backend from client components.
- Reuse the `src/components/salesbuff/` building blocks and the yellow/ink theme
  tokens in `src/styles.css`.

---

## 3. Before you push — checks

Run these and make sure they're clean for the files you touched:

```bash
# Backend: it must still import
cd SalesBuff && python -c "from salesbuff.api import app; print('ok')"

# Frontend: types + lint
cd SalesBuff/SalesBiff-Frontend
npx tsc --noEmit
npm run lint
```

> Note: `src/components/ui/form.tsx` has pre-existing type errors from the
> template — those are not caused by your change.

---

## 4. Commits & pull requests

- Branch off `main`: `git checkout -b feat/short-description`.
- Use clear, present-tense commit messages focused on the **why**
  (e.g. `fix: never let the seller become its own incumbent`).
- Keep PRs scoped. Describe what changed and how you tested it.
- **Never commit secrets.** `.env` files are git-ignored; if you add a new config
  value, add it to the matching `.env.example` instead.

---

## 5. Deploy / redeploy

Both hosts auto-deploy from `main` once connected.

### Backend → Render
- Root Directory: `SalesBuff`
- Build: `pip install -r salesbuff/requirements.txt`
- Start: `uvicorn salesbuff.api:app --host 0.0.0.0 --port $PORT`
- **Single instance** (in-memory job store + usage counter).
- Secrets: `OPENAI_API_KEY`, `TAVILY_API_KEY`, optional `COURTLISTENER_TOKEN`.
- Blueprint: [`render.yaml`](render.yaml).

### Frontend → Vercel
- Root Directory: `SalesBuff/SalesBiff-Frontend`
- Framework: Other (uses bundled `vercel.json` + Nitro `vercel` preset).
- Env: `SALESBUFF_API_URL` = the Render backend URL (no trailing slash).

After merging to `main`, verify:
1. Render `/health` returns `{"status":"ok"}`.
2. The Vercel app loads and a test run returns a brief.

---

## 6. Security checklist

- [ ] No API keys, tokens, or `.env` files in the diff.
- [ ] New config values added to `.env.example` (empty) — not real values.
- [ ] If a secret was ever exposed, it has been rotated.
