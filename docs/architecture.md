# Architecture

## The loop

```
1. User hits a problem on any page of the host product.
2. Widget collects screenshot + metadata, with private content blurred first.
3. Agent retrieves candidate solutions, then diagnoses with the screenshot.
4. Confidence gate decides: answer, hedge, or refuse to guess.
5. No fix -> pre-filled GitHub issue (or "Me too" on an existing one).
6. Dev closes the issue -> webhook -> agent drafts a user-facing solution.
7. Human approves -> published to the KB and committed to solutions/.
8. The next user with the same problem is answered in one step.
```

Steps 6 to 8 are the point. Without them this is a screenshot tool; with them
the knowledge base grows every time the team fixes something.

## Request path

| Endpoint | Purpose |
|---|---|
| `GET /api/suggestions` | Layer 1. Route + version matching, no model call. Instant. |
| `POST /api/analyze` | Layer 2. The agent pipeline. |
| `POST /api/rate` | helpful / not helpful, and the "raised a ticket anyway" signal. |
| `POST /api/tickets` | Creates a GitHub issue, or comments "+1" on a duplicate. |
| `GET /api/reports/mine` | Closes the loop for the reporter. |
| `POST /webhooks/github` | Signature-verified; a closed issue becomes a draft. |
| `/api/admin/*` | Drafts, approve, reject, tickets, stats. |

## Layers of retrieval

**Layer 1 (`page_suggestions`)** runs the moment the panel opens. It is a
route-pattern and version match over published solutions — no embedding, no
model, no latency. Most support questions are "this page is broken", and this
answers them before the user has taken a screenshot.

**Layer 2 (`semantic_candidates`)** embeds a query built from the comment,
console errors, failed requests and page title, then ranks published
solutions by cosine similarity, filtered to the same sub-product and a
version range covering the user's build. A route match adds a small bonus.

The two lists are merged and de-duplicated before they reach the model.

## Why the agent cannot hallucinate a fix

Three mechanisms, in order:

1. The prompt passes candidates as `[id] title: summary` and demands ids back.
2. `schema.validate_diagnosis` **drops every match whose id was not offered**.
3. With no surviving match, confidence is capped at 0.2, which lands below
   `CONFIDENCE_LOW` and routes to the ticket path.

So the worst case is an unnecessary ticket, never a made-up instruction.

## Ranking and the failure signal

`quality_weight` scores a solution as `helpful / (helpful + unhelpful +
ticket_after)`, clamped to `[0.5, 1.15]` with a floor of 0.85 for solutions
nobody has rated yet, so new entries are not buried.

`ticket_after_count` is the sharpest input. A user who marked a solution
helpful and then raised a ticket in the same session is telling you the
solution looked right and was not. That counts against it harder than a plain
"did not help".

## Degradation

Every external dependency has a path that keeps the demo alive:

| Fails | What happens |
|---|---|
| Model provider misconfigured | Falls back to the offline provider at startup |
| Model returns bad JSON | Validate, retry once, then the ticket path |
| Embedding call fails | Layer 1 suggestions still work |
| Screenshot upload fails | The report and ticket still go through |
| GitHub unreachable or no token | Dry-run tickets with database-allocated numbers |
| `html2canvas` fails | Falls back to `getDisplayMedia`, then to no image |

## Data model

`solutions` (the KB, with embeddings and version ranges) · `reports` (every
interaction) · `ratings` (including `raised_ticket`) · `tickets` (mirrored
from GitHub) · `events` (audit trail and stats).

Embeddings are stored as JSON, which keeps SQLite viable for a clean clone.
On Postgres the schema is unchanged; moving to a real `vector` column is
issue #1 in CONTRIBUTING.md.
