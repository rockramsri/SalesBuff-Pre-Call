# SalesBuff

## Backend

```bash
cd SalesBuff
pip install -r salesbuff/requirements.txt
uvicorn salesbuff.api:app --port 8000 --reload
```

Env: `salesbuff/.env` (see `salesbuff/.env.example`).

## Frontend

```bash
cd SalesBuff/SalesBiff-Frontend
npm install
npm run dev
```

Optional: `SALESBUFF_API_URL=http://127.0.0.1:8000` (defaults to that URL).
