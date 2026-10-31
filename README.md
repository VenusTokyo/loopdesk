# LoopDesk

**A screenshot becomes a solution. A ticket becomes the next user's answer.**

LoopDesk is a drop-in widget for any product. A user hits a problem, captures
the screen with one click, and an AI agent answers from the product's own
knowledge base — with a citation. If there is no known fix, the agent refuses
to guess and opens a GitHub issue carrying the screenshot, console errors and
failed requests. When a developer closes that issue, the agent drafts a
user-facing solution, a human approves it, and it is published to the
knowledge base **and committed back to the repository**.

The same problem never gets solved twice.

```
User hits issue → screenshot + metadata + comment → AI agent diagnoses
  → known solution shown (rate it) → helpful? done, ticket deflected
  → not helpful / no match → ticket auto-created in GitHub
  → dev fixes and closes → AI drafts a user-facing solution → dev approves
  → published to the KB + committed to the repo → next user gets it instantly
```

## Quickstart

```bash
docker compose up --build
```

Open <http://localhost:8000/demo/>. That is it — no API key, no database
server, no GitHub token. The default provider is a deterministic offline
model and GitHub runs in dry-run mode, so the entire loop works on a laptop
with no network.

<details>
<summary>Run it without Docker</summary>

```bash
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
python -m backend.seed.seed
uvicorn backend.app.main:app --reload
```

</details>

| URL | What it is |
|---|---|
| `/` | Landing page |
| `/demo/` | Acme Suite, the sample host product with seeded bugs |
| `/admin/` | Approve AI-drafted solutions (token: `dev-admin`) |
| `/docs` | OpenAPI reference |
| `/healthz` | Health and active configuration |

## Embedding it in your own product

One script tag:

```html
<script src="https://your-app.ondigitalocean.app/widget.js"
        data-api="https://your-app.ondigitalocean.app"
        data-key="your-key"
        data-subproduct="auto"
        data-blocklist="/settings/*,/billing/card"></script>
```

Optionally tell it who is looking at the page:

```html
<script>
  window.LOOPDESK_CONTEXT = {
    subproduct: 'analytics',
    app_version: '2.4.0',
    user_role: 'member',
  };
</script>
```

Mark anything that must never be captured:

```html
<span data-private>priya@northwind.example</span>
```

## What the agent actually does

`POST /api/analyze` runs a five-step pipeline in `backend/agent/`:

1. **Store** the screenshot (local disk or a private Spaces bucket) and the report.
2. **Retrieve** candidates in two layers — route/version matching, then
   embedding similarity — filtered to `status='published'`, the same
   sub-product, and a version range that covers the user's build.
3. **Diagnose** with a multimodal call: screenshot + comment + metadata +
   the candidate list, answering in strict JSON.
4. **Gate on confidence**. ≥0.7 with a citation shows the fix. 0.4–0.7 says
   "this might help". Below that it says *I could not find a known fix* and
   offers a ticket. It never invents steps.
5. **Check for duplicates** by embedding similarity against open tickets, and
   offers **"Me too"** on an existing issue instead of opening another.

Two guardrails make the citation real: the prompt passes solutions as
`[id] title: summary` and requires ids back, and
`backend/agent/schema.py` **drops any match citing an id that was not
offered**, then caps confidence at 0.2 when nothing survives. A hallucinated
fix cannot reach the user.

Prompts are plain markdown in `backend/agent/prompts/` — improve them with a
text editor.

## Swapping the model

`LLM_PROVIDER` picks one implementation of a two-method interface
(`vision_json`, `embed`):

| Value | Backend | Use |
|---|---|---|
| `mock` | offline, deterministic | default; demos and CI with no key |
| `gemma` | Gemma via the Gemini API | multimodal screenshot analysis |
| `openai_compat` | any OpenAI-compatible endpoint (Ollama, vLLM, a DigitalOcean GenAI endpoint) | fully self-hosted open weights |

Adding a provider means one file in `backend/agent/providers/`. Nothing else
in the codebase knows which model is running.

## Privacy

- `[data-private]` elements are masked **before** the pixels are rendered —
  `html2canvas` renders the DOM, so private content never exists in the image.
- Blocklisted routes do not render the widget at all. The capture code never
  loads on your payment page.
- Query strings are stripped from captured request URLs.
- Screenshots go to your own storage: local disk, or a private bucket with
  time-limited signed URLs. Never to a third party.

## Architecture

```
+---------------------------+        +------------------------------------------+
|   Host app (Acme Suite)   |        |  DigitalOcean                            |
|                           |  HTTPS |                                          |
|  Billing | Projects |     +------->+  App Platform: FastAPI                   |
|  Analytics | Settings     |        |   /api/suggestions  /api/analyze         |
|                           |        |   /api/rate  /api/tickets                |
|  +---------------------+  |        |   /webhooks/github   /admin              |
|  | LoopDesk widget     |  |        |                                          |
|  | (vanilla JS, 29 kB) |  |        |  Postgres (or SQLite)   Spaces (S3)      |
|  +---------------------+  |        +---------+--------------------+-----------+
+---------------------------+                  |                    |
                                     Gemma (Gemini API)        GitHub
                                     vision + reasoning   issues, webhooks,
                                                          solutions/ commits
```

Storage, model and ticket system are each behind one small interface, so any
of them can be replaced without touching the pipeline.

## Repository layout

```
landing/           landing page (index.html, theme.css, landing.js)
widget/src/        capture.js, metadata.js, ui.js, api.js, index.js
widget/dist/       widget.js (built with `node widget/build.js`, no bundler)
backend/app/       FastAPI routes, models, config
backend/agent/     pipeline, retrieval, schema validation, prompts, providers
backend/integrations/  github.py, storage.py
backend/seed/      seed_solutions.json + a one-command loader
demo-app/          Acme Suite
admin/             approval page
solutions/         published solution markdown, committed by the app
docs/              architecture, self-hosting, demo script, roadmap
```

## Tests

```bash
pytest backend/tests -q
```

Eleven tests cover the whole loop on SQLite with the offline provider: a
known issue is answered with a citation, an unknown one is *not* guessed at,
rating then ticketing counts against a solution, a closed issue drafts a
solution, approval publishes and commits it, and the next user gets it.

## Documentation

- [docs/architecture.md](docs/architecture.md) — how the pieces fit
- [docs/self-hosting.md](docs/self-hosting.md) — running on fully open weights
- [docs/github-setup.md](docs/github-setup.md) — connecting real tickets and the webhook
- [docs/deployment.md](docs/deployment.md) — DigitalOcean checklist
- [docs/demo-script.md](docs/demo-script.md) — the three-minute walkthrough
- [docs/roadmap.md](docs/roadmap.md) — what comes next
- [marketing.md](marketing.md) — pitch, taglines, slide outline, objections
- [CONTRIBUTING.md](CONTRIBUTING.md) — good first issues

## Licence

MIT. See [LICENSE](LICENSE).
