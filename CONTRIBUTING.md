# Contributing to LoopDesk

Thanks for looking. The project is small on purpose: one FastAPI service, one
vanilla-JS widget, no build step you have to learn.

## Set up

```bash
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
python -m backend.seed.seed
uvicorn backend.app.main:app --reload
```

Open <http://localhost:8000/demo/>. No API key is needed — `LLM_PROVIDER=mock`
is a deterministic offline provider, and GitHub runs in dry-run mode.

After editing anything in `widget/src/`:

```bash
node widget/build.js
```

Before opening a pull request:

```bash
pytest backend/tests -q
```

## Where things live

| You want to change | Look at |
|---|---|
| How the agent reasons | `backend/agent/prompts/*.md` |
| What counts as confident | `backend/agent/pipeline.py` (`_gate`) and `CONFIDENCE_*` in `.env` |
| How solutions are ranked | `backend/agent/retrieval.py` |
| Hallucination guard | `backend/agent/schema.py` |
| A new model backend | `backend/agent/providers/` |
| Widget behaviour | `widget/src/` |
| Ticketing / webhook | `backend/integrations/github.py`, `backend/app/routes/webhooks.py` |

## Good first issues

These are self-contained and each has a clear finish line.

1. **pgvector retrieval backend.** `retrieval.semantic_candidates` ranks in
   Python. Add a Postgres path using a real `vector` column and an ivfflat
   index, selected by database dialect. The interface must not change.
2. **A Jira or Linear ticket provider.** `integrations/github.py` is the only
   file that knows about issue trackers. Give it a sibling and a
   `TICKET_PROVIDER` setting.
3. **Automatic PII detection in capture.** Today redaction is opt-in via
   `[data-private]`. Add a client-side pass that blurs things that *look* like
   emails, card numbers and phone numbers.
4. **Solution expiry.** `applies_from` / `applies_to` are stored and filtered,
   but nothing deprecates a solution when a release supersedes it.
5. **Insights dashboard.** `/api/admin/stats` returns deflection rate and
   counts. Turn it into a page: top issues per sub-product, pages that confuse
   people most, time from ticket to published solution.
6. **Reporter notifications.** `GET /api/reports/mine` already knows when a
   user's report was fixed. Add an opt-in email or web push.
7. **Widget accessibility pass.** Focus trapping in the panel, Escape to
   close, and a screen-reader audit of the result cards.

## Pull requests

- One change per PR, with a line in the description on what you verified.
- Add a test when you change agent behaviour — `backend/tests/test_loop.py`
  is the model for it.
- Prompt changes: say which of the three demo bugs you re-ran and what the
  confidence was before and after.
- Keep the widget dependency-free. `html2canvas` is loaded lazily from a CDN
  and is the only external piece.

## Code of conduct

Be decent. Assume good faith. Disagreement about design is welcome;
disrespect is not.
