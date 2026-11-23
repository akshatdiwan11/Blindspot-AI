# Running and deploying

## Option 1: Docker (everything on one machine)

```bash
cp .env.example .env        # optional: add OPENAI_API_KEY for the AI investigator
docker compose up --build
```

Open <http://localhost:8080>. The API is also exposed on <http://localhost:8000/api/docs>.
Data lives in the `pgdata` Docker volume and survives restarts (`docker compose down` keeps it;
`docker compose down -v` deletes it).

## Option 2: Local development

Requirements: Python 3.13, Node 20 or newer, PostgreSQL 14 or newer (tested with Python 3.13, Node 22 and PostgreSQL 16).

```bash
# database
createuser blindspot -P            # password: blindspot
createdb blindspot -O blindspot

# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload       # http://localhost:8000/api/docs

# frontend (second terminal)
cd frontend
npm install
npm run dev                         # http://localhost:5173 (proxies /api to :8000)
```

Settings are read from environment variables or `backend/.env`; see `.env.example`.

## Option 3: Free hosting on Render + Cloudflare

The API and database run on Render; the website runs as a Cloudflare Worker that also forwards
`/api/*` to Render, so the browser only talks to one address.

### 1. API and database on Render

1. In Render choose **New → Blueprint** and pick this repository. Render reads `render.yaml`
   and creates the `blindspot-ai-api` web service (Docker) and the `blindspot-ai-db` database.
2. Optionally fill in `OPENAI_API_KEY` when asked (it can be added later under Environment).
3. Wait for the deploy, then open `https://<your-service>.onrender.com/api/health`; it should
   return `{"status":"ok"}`. Database migrations run automatically on every start.

### 2. Website on Cloudflare

1. If Render named the service something other than `blindspot-ai-api`, edit `API_ORIGIN` in
   `wrangler.jsonc` to your Render URL.
2. In Cloudflare choose **Workers & Pages → Create → Import a repository** and pick this
   repository. Use build command `npm run build` and deploy command `npx wrangler deploy`
   (both are the defaults Cloudflare detects from `package.json` and `wrangler.jsonc`).
3. Open the `*.workers.dev` address Cloudflare gives you.

Notes on the free plans: the Render service sleeps after inactivity and takes about a minute to
wake (the site shows "The analysis server is starting up" meanwhile), and the free Render
database expires after 30 days unless upgraded.

## Running the tests

```bash
cd backend && pytest                       # 67 tests, uses a temporary SQLite database
TEST_DATABASE_URL=postgresql+psycopg2://blindspot:blindspot@localhost:5432/blindspot_test pytest   # same suite on PostgreSQL
cd frontend && npm test && npm run typecheck
python scripts/run_benchmarks.py          # benchmark recovery + null control (from the repo root)
```
