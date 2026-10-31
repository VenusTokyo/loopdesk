# Demo script (about 3 minutes)

Have open: `/demo/billing/`, `/demo/analytics/`, the GitHub repository,
`/admin/` with the token already entered.

## 1. The problem (20s)

"Users hit issues. They describe them badly, support guesses, and developers
fix the same thing twice. The fix exists — it is just locked in a closed
ticket nobody can search."

## 2. A known issue (45s)

On `/demo/billing/`, click **Export invoices (CSV)**. It fails.

Open the widget. **Point out that solutions are already listed** before any
screenshot — that is route matching, no AI, no latency.

Take a screenshot, type "export keeps failing", click **Get a solution**.
The agent returns the seeded fix with a confidence badge and a citation.

Show the preview: the customer name and email are solid blocks. That
happened before the image existed, because we render the DOM, not the
screen - the real values were never in the picture.

Rate it **This helped**.

## 3. Safety (15s)

Go to `/demo/settings/payment/`. The widget button is not there. The route is
blocklisted, so the capture code never loads on a page with card data.

## 4. An unknown issue (60s)

On `/demo/analytics/`, click **Break it**, then change the date range. It
silently snaps back to Last 7 days.

Open the widget, capture, comment "the filter will not stay on 30 days".

**This is the important moment.** The agent says it could not find a known
fix. It does not guess. It offers a pre-filled ticket instead — and because
issue #42 is already open for this, it offers **"Me too"** rather than a
duplicate.

Take the ticket path. Show the created GitHub issue: diagnosis, the user's
own words, a metadata table, the console error, the failed request, labels,
and the assignee from `owners.yml`.

## 5. Resolution (30s)

Close that issue in GitHub.

The webhook fires. Open `/admin/` — an AI-drafted, user-facing solution is
waiting, with stack traces and file paths stripped out. Edit a word to show
the human stays in the loop. Click **Approve and publish**.

Show `solutions/analytics/....md` now committed in the repository.

## 6. The payoff (20s)

Go back to `/demo/analytics/`, reproduce the bug, open the widget. The
solution that did not exist two minutes ago is **already listed under "Known
issues on this page"** — layer 1, no model call, no latency. Capture and ask,
and the agent cites it too. The original reporter's **My reports** tab now
says it was fixed.

> On the offline provider the page-suggestion payoff is deterministic. The
> agent's own confidence on a *differently worded* second report depends on
> the model: run the demo on `LLM_PROVIDER=gemma` if you want that beat too.

"Every ticket the team closes makes the product answer for itself. Next:
real multi-product integration, an insights dashboard, version-aware expiry
and automatic PII redaction."

## If something fails live

- Model or network down: `LLM_PROVIDER=mock` runs the whole thing offline.
- No GitHub token: dry-run tickets still flow through the webhook, drafting
  and approval, and the solution file is written locally.
- Worst case: play the recorded backup video.
