<!-- 🟡 SalesBuff -->

[![CI](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/ci.yml/badge.svg)](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/ci.yml)
[![CodeQL](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/codeql.yml/badge.svg)](https://github.com/rockramsri/SalesBuff-Pre-Call/actions/workflows/codeql.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-brightgreen?logo=dependabot)](https://github.com/rockramsri/SalesBuff-Pre-Call/security/dependabot)

# 🟡 SalesBuff — Pre-call due-diligence intelligence

> Speak your account scenario, and SalesBuff hands a sales rep two things before
> the call: **Action tips** (what to say, ask, show, avoid) and a **Fact dossier**
> (what's verifiably true, with sources).

SalesBuff turns a one-line meeting description into a skim-ready pre-call brief.
It resolves the real companies and people involved, researches them across the
web and court records, and produces a **citation-grounded** brief — no chat, no
fluff.

---

## What it does

You give it something like:

> *"Meeting Dr. Lee Schwamm at Yale New Haven Health tomorrow. We're expanding
> our AI clinical-documentation rollout to more physicians."*

…and it returns:

| Tab | What you get |
|-----|--------------|
| **Actions** | Conversation **moves** grouped by call flow — opening move, pain hypothesis, differentiation, proof point, next step. Each is something to *say / ask / show / avoid / verify*, with a talk-track and sources. |
| **Facts** | An **evidence dossier** grouped into domain categories (priorities, pain signals, stakeholders, legal/regulatory, open questions), every finding backed by a source URL. |

Both come from **one** shared research pass, so the two tabs always agree on the
evidence.

---

## Repository layout

```
SalesBuff-Pre-Call/                ← this repo (git root)
├── README.md                      ← you are here
├── CONTRIBUTING.md                ← how to contribute / push / deploy
├── render.yaml                    ← Render blueprint for the backend
└── SalesBuff/
    ├── README.md                  ← backend guide (Python / FastAPI)
    ├── salesbuff/                 ← the Python package (the API + pipeline)
    └── SalesBiff-Frontend/
        ├── README.md              ← frontend guide (TanStack Start)
        └── ...
```

- **Backend** — Python + FastAPI. Entity resolution → web + legal research →
  two LLM lanes (Actions + Facts). See [`SalesBuff/README.md`](SalesBuff/README.md).
- **Frontend** — TanStack Start + Vite + React + Tailwind. Speak/type a scenario,
  run, and read the brief. See [`SalesBuff/SalesBiff-Frontend/README.md`](SalesBuff/SalesBiff-Frontend/README.md).
- **Architecture deep-dive** — [`SalesBuff/ARCHITECTURE.md`](SalesBuff/ARCHITECTURE.md).

---

## Quickstart (local)

Run the two services in separate terminals.

**1) Backend** (needs OpenAI + Tavily keys)

```bash
cd SalesBuff
pip install -r salesbuff/requirements.txt
cp salesbuff/.env.example salesbuff/.env   # then fill in your keys
uvicorn salesbuff.api:app --port 8000 --reload
```

**2) Frontend**

```bash
cd SalesBuff/SalesBiff-Frontend
npm install
npm run dev            # talks to http://127.0.0.1:8000 by default
```

Open the printed local URL, describe an account, and hit **Run due diligence**.

> 🟡 **No keys?** The UI also lets a user paste their **own** OpenAI + Tavily keys
> (kept in the browser tab only) to run without touching the shared quota.

---

## How the pieces talk

```
Browser ──► Frontend server fns ──► Backend API ──► OpenAI + Tavily + CourtListener
                (SALESBUFF_API_URL)
```

The browser never calls the backend directly — TanStack server functions proxy
to it, so the backend URL and any keys stay off the client.

---

## Deployment

| Part | Host | Notes |
|------|------|-------|
| Backend | **Render** | Web service, **Root Directory = `SalesBuff`**. Blueprint in [`render.yaml`](render.yaml). Long jobs + in-memory state → keep **1 instance**. |
| Frontend | **Vercel** | **Root Directory = `SalesBuff/SalesBiff-Frontend`**, Nitro `vercel` preset (set in `vite.config.ts`). Set `SALESBUFF_API_URL` to the Render URL. |

Full steps and env vars are in [`CONTRIBUTING.md`](CONTRIBUTING.md) and each
sub-README.

---

## Security

- **Never commit secrets.** `.env` files are git-ignored — use `.env.example` as
  the template and set real values in Render / Vercel.
- If a key is ever exposed, **rotate it** immediately.
