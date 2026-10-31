# Deploy to DigitalOcean — fast path

Your laptop keeps running for the demo. This is a second, public copy.

## 1. Create the app (~3 minutes of clicking)

1. <https://cloud.digitalocean.com/apps> → **Create App**
2. Source: **GitHub** → authorise → pick **VenusTokyo/loopdesk**, branch `main`
3. It detects Python. Override these two if it guessed differently:
   - Build command: `pip install -r backend/requirements.txt`
   - Run command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
4. HTTP port: **8080**
5. Plan: the smallest Basic instance is enough.

(Or skip the wizard: **Create App → Import from App Spec** and paste
`.do/app.yaml` from this repo.)

## 2. Environment variables

Plain values:

| Key | Value |
|---|---|
| `LLM_PROVIDER` | `gemma` |
| `GEMINI_MODEL` | `gemma-4-26b-a4b-it` |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` |
| `DATABASE_URL` | `sqlite:///./data/loopdesk.db` |
| `STORAGE_BACKEND` | `local` |
| `GITHUB_REPO` | `VenusTokyo/loopdesk-demo-tickets` |
| `GITHUB_SOLUTIONS_REPO` | `VenusTokyo/loopdesk` |
| `DEMO_DUPLICATE_ISSUE` | `1` |
| `CORS_ORIGINS` | `*` |
| `PUBLIC_BASE_URL` | `${APP_URL}` |

Mark these **Encrypt** (same values as your local `.env`):

`GEMINI_API_KEY` · `GITHUB_TOKEN` · `GITHUB_WEBHOOK_SECRET` · `ADMIN_TOKEN`

## 3. Seed it once after the first deploy

Console tab on the `web` component:

```
python -m backend.seed.seed --reset
```

The app spec also defines a PRE_DEPLOY job that does this automatically.

## 4. Check

- `https://<your-app>.ondigitalocean.app/healthz` → `"provider":"gemma"`
- `https://<your-app>.ondigitalocean.app/` → the landing page

## 5. The webhook — this is what the deploy buys you

With a public URL, GitHub can finally reach you, so **step 4 of the demo
stops needing the terminal command**.

In **VenusTokyo/loopdesk-demo-tickets** → Settings → Webhooks → Add webhook:

| Field | Value |
|---|---|
| Payload URL | `https://<your-app>.ondigitalocean.app/webhooks/github` |
| Content type | `application/json` |
| Secret | the same string as `GITHUB_WEBHOOK_SECRET` |
| Events | Issues, and Pull requests |

Closing an issue now creates the draft by itself.

## Known limits of this deploy

- The filesystem is **ephemeral**. SQLite and screenshots are wiped on every
  deploy and restart. Fine for a demo; for anything real attach Managed
  Postgres and set `STORAGE_BACKEND=spaces`.
- The first request after a cold start is slow.
- Gemma 4 has been returning intermittent 500s today. The app retries and
  falls back to the sibling model, but a call can still take ~35s.

## If the deploy misbehaves mid-demo

Use your laptop. It is already working and nothing about the deploy touches it.
