# Roadmap

What this is not yet, and what it becomes.

## Known limits today

- Single tenant. One API key, one knowledge base, no SSO.
- Redaction is opt-in: `[data-private]` and route blocklists only.
- Retrieval ranks in Python. Fine for hundreds of solutions, not millions.
- Solutions carry a version range but nothing expires them automatically.
- The reporter learns of a fix only by reopening the widget.

## Next

1. **Real product integration** via the embeddable SDK and a GitHub App
   (per-installation tokens instead of a PAT).
2. **Client-side PII detection** beyond `data-private`, plus per-tenant
   isolation of screenshots and knowledge bases.
3. **Version-aware expiry** tied to releases: when a fix ships, solutions it
   supersedes are deprecated automatically.
4. **Insights dashboard**: deflection rate over time, top issues per
   sub-product, the pages that confuse people most, time from report to
   published solution.
5. **Reporter notifications** when their ticket is fixed.
6. **Connectors** for Jira, Linear and Slack behind the same interface that
   GitHub uses today.
7. **Developer assist**: suggest likely files and a fix outline on the ticket
   itself, from the screenshot, the stack trace and the repository.

## Deliberately out of scope

Video capture, a mobile SDK, and a full analytics product. The value is the
loop, not the capture tooling.
