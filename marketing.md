# LoopDesk — pitch material

Everything here is backed by something that actually runs. If a claim is not
demonstrable in the three-minute demo, it is not in this file.

---

## The one-liner

**LoopDesk turns every closed ticket into the next user's answer.**

Longer, when you have a breath more:

> A drop-in widget for any product. The user screenshots the problem, an AI
> agent answers from the product's own knowledge base with a citation — and
> when there is no answer, the ticket it opens becomes one the moment a
> developer closes it.

---

## The problem, in one slide

Support today is a bucket with a hole in it.

1. A user hits a problem and describes it badly. "It's broken."
2. Support guesses, asks for screenshots, asks what browser, asks again.
3. It becomes a ticket. A developer fixes it and closes it.
4. **The fix dies in that closed ticket.** It is not searchable, not written
   for users, not connected to the page where the problem happens.
5. Next month, a different user hits the same thing. Go to step 1.

The fix exists. It is just locked somewhere no user will ever look.

**The cost:** support time on already-solved problems, developer time on
duplicate tickets, and users who conclude the product is broken.

---

## What LoopDesk does differently

Most support tooling helps you *answer faster*. LoopDesk is built so the
same question stops being asked.

| | Typical support widget | LoopDesk |
|---|---|---|
| Input | user types a description | screenshot + console errors + failed requests, collected automatically |
| Knowledge | a help centre someone has to maintain | grows itself from closed tickets |
| When it does not know | guesses, or dumps you in a chat queue | **says so**, and opens a ticket with full context |
| Where the fix lives | a SaaS silo | your database *and* committed to your repo as markdown |
| After the fix ships | nothing | published to the KB, returned to the next user, reporter told |

The loop is the product:

```
user hits issue → screenshot + metadata → agent diagnoses
  → known fix shown, cited → helpful? ticket deflected
  → no match → ticket opened in GitHub with full context
  → dev fixes and closes → agent drafts a user-facing solution
  → human approves → published to KB + committed to the repo
  → next user gets it instantly
```

---

## Three things to say out loud in the demo

**1. "It refuses to guess."**

This is the counterintuitive one, and it is the strongest. On the unsolved
Analytics bug the agent returns *"I could not find a known fix"* instead of
inventing plausible steps. Three mechanisms make a hallucinated fix
impossible: candidate solutions are passed with ids, the validator **drops
any citation to an id that was not offered**, and with nothing left the
confidence is capped below the gate. The worst case is an unnecessary
ticket, never a made-up instruction.

Everyone demos an AI that answers. Demo one that knows when to shut up.

**2. "Private data is never in the picture."**

`[data-private]` fields are masked *before the pixels exist* — we render the
DOM, not the screen. And on the payment page the widget is not merely
hidden: the route is blocklisted, so the capture code never loads at all.
Open devtools on `/demo/settings/payment/` and show `window.LoopDesk` is
`undefined`.

**3. "Watch the knowledge base grow."**

Close the GitHub issue on stage. The webhook fires, an AI draft appears in
the admin page with stack traces stripped out, a human approves it, and the
solution is committed to the repository as
`solutions/analytics/....md`. Reload the widget: a solution that did not
exist ninety seconds ago is now listed on the page.

---

## Prize-track alignment

### Best Use of Gemma 4

- **Genuinely multimodal, not decorative.** The screenshot is reasoned over
  alongside the user's comment, console errors, failed network requests,
  route, role and app version — and grounded against retrieved candidate
  solutions.
- **Structured output under constraint.** Strict JSON with intent,
  diagnosis, cited solution ids, calibrated confidence and a ticket
  decision. Validated, retried once, then an honest fallback.
- **Confidence used for something.** It is not a number on a card — it gates
  three different user experiences at 0.7 and 0.4.
- **Prompts are in the repo** as plain markdown, so the judging panel can
  read exactly what the model was asked.

### Best Open-Source AI Project (DigitalOcean)

- **MIT, one command.** `docker compose up --build` from a clean clone, no
  API key, no database server, no GitHub token. It works offline.
- **Model-pluggable by design.** A two-method interface (`vision_json`,
  `embed`). Gemma via the Gemini API, or any OpenAI-compatible endpoint —
  Ollama, vLLM, a DigitalOcean GenAI endpoint. Adding a provider is one
  ~40-line file.
- **Self-hostable end to end.** Point the provider at your own endpoint and
  storage at local disk, and nothing leaves your infrastructure.
- **Built to be contributed to.** `CONTRIBUTING.md` ships seven scoped good
  first issues, each with a clear finish line — a pgvector backend, a
  Jira/Linear provider, client-side PII detection, solution expiry, an
  insights dashboard, reporter notifications, an accessibility pass.
- **DigitalOcean throughout:** App Platform for the service, Managed
  Postgres for the knowledge base, Spaces with private ACLs and signed URLs
  for screenshots, and an optional droplet for open weights.

---

## Taglines

Pick one and commit to it.

- **Every ticket you close answers the next user.** *(recommended)*
- Screenshot in. Solution out. Loop closed.
- The support tool that puts itself out of a job.
- Your closed tickets are a knowledge base. LoopDesk unlocks them.
- It knows what it does not know.

---

## Slide outline (6 slides, ~3 minutes)

1. **The hole in the bucket** — the five-step loop above, with step 4 in red.
2. **One script tag** — the embed snippet, and the widget on a real page.
3. **The agent** — the pipeline diagram and the confidence gate at 0.7 / 0.4.
4. **It refuses to guess** — screenshot of the "no known fix" state next to
   the hallucination guard in `schema.py`.
5. **The loop closes** — issue closed → draft → approved → committed file →
   next user served. Four screenshots, one arrow each.
6. **Open source on DigitalOcean** — architecture with the services named,
   the provider interface, MIT, `docker compose up`.

Live demo sits between slides 3 and 5. Follow `docs/demo-script.md`.

---

## Objections, and honest answers

**"Isn't this just Sentry / Intercom / a feedback widget?"**
Those capture problems. None of them close the loop back into the product's
knowledge base. The screenshot is the cheap half; drafting a user-facing
solution from a closed ticket and committing it to the repo is the half
nobody does.

**"Why would users trust an AI answer?"**
They do not have to. Every answer cites a knowledge-base entry a human
approved, and the agent escalates rather than guessing. The citation is
enforced in code, not by a prompt.

**"What if the AI writes a bad solution from the ticket?"**
It cannot publish. Drafts land in an approval page where a developer edits
or rejects them. The AI does the writing; a human does the publishing.

**"What about screenshots of sensitive data?"**
Route blocklists stop capture entirely on sensitive pages, `[data-private]`
is masked before rendering, query strings are stripped from captured request
URLs, and images go to your own storage. Automatic PII detection is on the
roadmap and listed as a good first issue — we are not claiming it today.

**"Does this scale?"**
Retrieval ranks in Python today, which is fine for hundreds of solutions and
honest about it. pgvector is a drop-in replacement behind the same function
and is issue #1 in CONTRIBUTING.

**"How hard is it to adopt?"**
One `<script>` tag, plus an optional context object. Nothing else in the
host app changes.

---

## Social copy

**Short (X / LinkedIn):**

> Built LoopDesk at Hack Day Delhi: a widget where users screenshot a bug and
> an AI agent answers from the product's own knowledge base — with a citation,
> or an honest "I don't know" plus a pre-filled GitHub issue.
>
> The part I like: when a dev closes that issue, the agent drafts the
> user-facing fix, a human approves it, and it's committed to the repo. The
> next user with that bug gets an answer instantly.
>
> MIT, runs offline with `docker compose up`. Gemma for vision, swappable for
> any open-weight model you host yourself.

**Repo description (GitHub, 120 chars):**

> Screenshot-to-solution widget. An AI agent answers from your KB, or opens a
> ticket that becomes the next answer. MIT.

**Submission blurb (~80 words):**

> LoopDesk is a drop-in widget that closes the support loop. A user captures a
> screenshot; the agent diagnoses it against the product's knowledge base using
> Gemma's multimodal reasoning, and answers with a citation or refuses to guess
> and files a GitHub issue carrying the console errors and failed requests.
> When a developer closes that issue, the agent drafts the user-facing
> solution, a human approves it, and it is published to the knowledge base and
> committed to the repo. MIT, self-hostable, one command.

---

## Do not say

- "Replaces your support team." It deflects known issues and escalates the
  rest. Say that instead.
- "100% accurate" / "never wrong." The whole pitch is that it knows its
  limits. Undercutting that costs more than it gains.
- "Fully automated." A human approves every published solution, on purpose.
- Anything about multi-tenancy, SSO or the insights dashboard as if it ships
  today. They are roadmap, and `docs/roadmap.md` says so.
