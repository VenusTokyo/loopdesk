# Connecting the GitHub loop

Until a token is configured LoopDesk runs in **dry-run**: tickets are mirrored
in the local database with synthetic numbers, the webhook and approval flow
still work, and approved solutions are written to disk instead of committed.
That is enough to demo everything except real issues. This page turns it on.

## 1. Create a fine-grained token

<https://github.com/settings/personal-access-tokens/new>

| Field | Value |
|---|---|
| Token name | `loopdesk-demo` |
| Resource owner | your account or org |
| Expiration | through the event, not "no expiration" |
| Repository access | **Only select repositories** → the tickets repo **and** the product repo |

Permissions:

| Repository | Permission | Access |
|---|---|---|
| tickets repo | Issues | Read and write |
| tickets repo | Metadata | Read-only (added automatically) |
| product repo | Contents | Read and write |

Issues write is what opens tickets and posts "Me too" comments. Contents write
on the product repo is what commits `solutions/<subproduct>/<slug>.md` when a
draft is approved. Nothing else is needed - no `workflow`, no `admin`, no
access to your other repositories.

## 2. Put it in `.env`

```ini
GITHUB_TOKEN=github_pat_...
GITHUB_REPO=<owner>/loopdesk-demo-tickets
GITHUB_SOLUTIONS_REPO=<owner>/loopdesk
DEMO_DUPLICATE_ISSUE=1
```

`.env` is git-ignored. Never commit a token; if one is ever pushed, revoke it
rather than removing it in a later commit - the history keeps it.

## 3. Restart and check

```bash
curl http://localhost:8000/healthz
```

`"github":"live"` means it is connected. `"dry-run"` means the token or the
repo is missing.

## 4. The webhook

The webhook needs a URL GitHub can reach, so it cannot point at localhost.
Either deploy first, or tunnel:

```bash
npx smee-client --url https://smee.io/<your-channel> --target http://localhost:8000/webhooks/github
```

Then in the **tickets** repo: Settings → Webhooks → Add webhook

| Field | Value |
|---|---|
| Payload URL | `https://<your-host>/webhooks/github` |
| Content type | `application/json` |
| Secret | the same string as `GITHUB_WEBHOOK_SECRET` |
| Events | Issues, and Pull requests |

Deliveries are signature-verified. A mismatched secret returns 401, and the
Recent Deliveries tab on the webhook page shows exactly what was sent.

## 5. End-to-end check

1. On `/demo/analytics/` click **Break it**, change the range, open the
   widget, capture, and raise the ticket.
2. A real issue appears in the tickets repo, labelled and assigned.
3. Close it. The webhook fires.
4. A draft appears in `/admin/`. Approve it.
5. `solutions/analytics/<slug>.md` is committed to the product repo.
6. Reopen the widget on that page - the new solution is listed.

## Revoking

Delete the token at <https://github.com/settings/personal-access-tokens>.
LoopDesk falls back to dry-run on the next request; nothing breaks.
