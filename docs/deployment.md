# Deploying on DigitalOcean

One App Platform service serves the API, the widget bundle, the demo app and
the admin page. Fewer moving parts is deliberate: a single deploy is hard to
get wrong on the day.

## Checklist

- [ ] **App Platform** service from this repository. Run command:
      `uvicorn backend.app.main:app --host 0.0.0.0 --port 8080`
      (App Platform injects `PORT`; set `--port $PORT` if you prefer).
- [ ] **Managed Postgres**, then set `DATABASE_URL` to the connection string
      with `+psycopg`:
      `postgresql+psycopg://user:pass@host:25060/db?sslmode=require`.
      For pgvector: `CREATE EXTENSION IF NOT EXISTS vector;`
      (SQLite is a supported fallback if the database eats time.)
- [ ] **Spaces** bucket, private ACL. Set `STORAGE_BACKEND=spaces` plus
      `SPACES_BUCKET`, `SPACES_REGION`, `SPACES_ENDPOINT`, `SPACES_KEY`,
      `SPACES_SECRET`. Screenshots are served through signed URLs.
- [ ] **Secrets**: `GEMINI_API_KEY`, `GITHUB_TOKEN`,
      `GITHUB_WEBHOOK_SECRET`, `ADMIN_TOKEN`, `DATABASE_URL`, Spaces keys.
- [ ] **`PUBLIC_BASE_URL`** set to the deployed URL — screenshot links in
      tickets are built from it.
- [ ] **`CORS_ORIGINS`** set to the host app's origin (not `*` in production).
- [ ] **GitHub webhook** pointed at `https://<app>/webhooks/github`,
      content type `application/json`, same secret, events: Issues and
      Pull requests.
- [ ] **Seed** once after the first deploy: `python -m backend.seed.seed`.
- [ ] **Health check** path `/healthz` — it reports the active provider,
      storage backend and whether GitHub is live or dry-run.

## Optional: self-hosted model

Run an open-weight model on a GPU droplet or a DigitalOcean GenAI endpoint and
switch with `LLM_PROVIDER=openai_compat`. See
[self-hosting.md](self-hosting.md). Re-seed afterwards so embeddings match.

## Verifying a deploy

```bash
curl https://<app>/healthz
curl "https://<app>/api/suggestions?route=/demo/billing/&subproduct=billing&version=2.4.0"
```

The first should report your provider and `"github":"live"`. The second
should return the seeded Billing solutions. Then open `/demo/` and run the
demo script end to end once before you need it.
