# PolicyPulse

Regulatory intelligence monitor for USCIS policy content.

PolicyPulse retrieves, normalizes, and persists USCIS regulatory content using Bright Data APIs.

---

## Setup

1. Clone the repository and create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Copy the environment template and fill in your values:

```bash
cp .env.example .env
```

3. Ensure PostgreSQL is reachable at the `DATABASE_URL` you configure (Supabase or local).

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `BRIGHT_DATA_API_KEY` | Bright Data API key |
| `BRIGHT_DATA_SERP_ZONE` | Bright Data SERP zone (default: `serp_api1`) |
| `BRIGHT_DATA_UNLOCKER_ZONE` | Bright Data Web Unlocker zone (default: `web_unlocker1`) |
| `ENVIRONMENT` | Runtime environment (`development`, `staging`, `production`) |

See [`.env.example`](.env.example) for the full template.

---

## Running locally

Start the development server:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/
# {"status":"ok","service":"PolicyPulse"}
```

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Deployment

PolicyPulse is configured for [Railway](https://railway.app/) via [`railway.toml`](railway.toml).

1. Create a new Railway project and connect this repository.
2. Set environment variables from `.env.example` in the Railway dashboard.
3. Railway uses Nixpacks to build and runs:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Ensure `DATABASE_URL` points to your production PostgreSQL instance before deploying.
