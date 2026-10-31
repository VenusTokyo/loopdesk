"""GitHub Issues as the ticket system, plus committing published solutions back.

With no GITHUB_TOKEN the client runs in dry-run mode: issues are mirrored in
the local database and given fake numbers, so the whole loop - including the
webhook, drafting and approval - can be demonstrated offline.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from pathlib import Path
from typing import Any

import httpx
import yaml

from ..app.config import REPO_ROOT, settings

log = logging.getLogger(__name__)
API = "https://api.github.com"
_OWNERS_PATH = REPO_ROOT / "owners.yml"


def load_owners() -> dict[str, Any]:
    if not _OWNERS_PATH.exists():
        return {"defaults": {"assignees": [], "labels": []}, "subproducts": {}}
    return yaml.safe_load(_OWNERS_PATH.read_text(encoding="utf-8")) or {}


def routing_for(subproduct: str) -> tuple[list[str], list[str]]:
    """-> (labels, assignees) for a sub-product."""
    cfg = load_owners()
    defaults = cfg.get("defaults") or {}
    entry = (cfg.get("subproducts") or {}).get(subproduct) or {}
    labels = list(defaults.get("labels") or []) + list(entry.get("labels") or [])
    assignees = list(entry.get("assignees") or defaults.get("assignees") or [])
    return labels, assignees


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    """GitHub signs every webhook delivery; an unverified one is not ours."""
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


class DryRunGitHub:
    """Stands in for the API when no token is configured."""

    enabled = False

    def create_issue(self, title: str, body: str, labels, assignees) -> dict[str, Any]:
        # The issue number is allocated by the caller from the database, so it
        # stays unique across restarts.
        log.info("[dry-run] would open issue: %s", title)
        return {"number": None, "html_url": None, "title": title, "dry_run": True}

    def comment(self, number: int, body: str) -> dict[str, Any]:
        log.info("[dry-run] would comment on #%s", number)
        return {"id": 0, "dry_run": True}

    def get_issue(self, number: int) -> dict[str, Any]:
        return {"number": number, "title": "", "body": "", "labels": [], "comments_list": []}

    def put_file(self, path: str, content: str, message: str) -> dict[str, Any]:
        local = settings.solutions_root / path
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(content, encoding="utf-8")
        log.info("[dry-run] wrote %s locally instead of committing", path)
        return {"path": path, "dry_run": True, "local_path": str(local)}


class GitHubClient:
    enabled = True

    def __init__(self) -> None:
        self.repo = settings.github_repo
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=30, headers=self.headers, base_url=API)

    def create_issue(self, title: str, body: str, labels, assignees) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title[:250], "body": body}
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees
        with self._client() as c:
            r = c.post(f"/repos/{self.repo}/issues", json=payload)
            r.raise_for_status()
            data = r.json()
        return {"number": data["number"], "html_url": data["html_url"], "title": data["title"]}

    def comment(self, number: int, body: str) -> dict[str, Any]:
        with self._client() as c:
            r = c.post(f"/repos/{self.repo}/issues/{number}/comments", json={"body": body})
            r.raise_for_status()
            return r.json()

    def get_issue(self, number: int) -> dict[str, Any]:
        with self._client() as c:
            r = c.get(f"/repos/{self.repo}/issues/{number}")
            r.raise_for_status()
            issue = r.json()
            cr = c.get(f"/repos/{self.repo}/issues/{number}/comments")
            issue["comments_list"] = cr.json() if cr.status_code == 200 else []
        return issue

    def put_file(self, path: str, content: str, message: str) -> dict[str, Any]:
        """Create or update a file via the contents API.

        Solutions are committed to `solutions_repo`, which defaults to the
        ticket repo but is usually the product repo - the knowledge base
        belongs next to the code, not in the triage queue.
        """
        repo = settings.solutions_repo
        with self._client() as c:
            sha = None
            head = c.get(f"/repos/{repo}/contents/{path}")
            if head.status_code == 200:
                sha = head.json().get("sha")
            payload = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode(),
            }
            if sha:
                payload["sha"] = sha
            r = c.put(f"/repos/{repo}/contents/{path}", json=payload)
            r.raise_for_status()
            return r.json()


def get_github() -> GitHubClient | DryRunGitHub:
    if settings.github_enabled:
        return GitHubClient()
    log.info("GITHUB_TOKEN/GITHUB_REPO not set - running GitHub integration in dry-run mode")
    return DryRunGitHub()


def solution_markdown(sol) -> str:
    """The file committed to solutions/<subproduct>/<slug>.md."""
    front = [
        "---",
        f"title: {sol.title}",
        f"subproduct: {sol.subproduct}",
        f"source: {sol.source}",
    ]
    if sol.source_issue_number:
        front.append(f"issue: {sol.source_issue_number}")
    if sol.applies_from:
        front.append(f"applies_from: {sol.applies_from}")
    if sol.applies_to:
        front.append(f"applies_to: {sol.applies_to}")
    front += [f"routes: {sol.route_patterns or []}", "---", ""]
    return "\n".join(front) + f"# {sol.title}\n\n{sol.summary}\n\n## Steps\n\n{sol.steps_md}\n"


def solution_path(sol) -> str:
    slug = slugify(sol.title)
    return f"solutions/{sol.subproduct or 'general'}/{slug}.md"


def slugify(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in (text or "solution")]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60] or "solution"


def local_solution_file(sol) -> Path:
    return settings.solutions_root / solution_path(sol)
