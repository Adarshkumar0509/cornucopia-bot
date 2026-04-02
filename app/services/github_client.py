import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubClient:
    """Thin async wrapper around the GitHub REST API."""

    def __init__(self):
        self._headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._owner = settings.repo_owner
        self._repo = settings.repo_name

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    async def post_comment(self, issue_number: int, body: str) -> None:
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}/comments"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._headers, json={"body": body})
            resp.raise_for_status()
            logger.info("Posted comment on issue #%s", issue_number)

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    async def add_label(self, issue_number: int, label: str) -> None:
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}/labels"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._headers, json={"labels": [label]})
            resp.raise_for_status()
            logger.info("Added label '%s' to issue #%s", label, issue_number)

    async def remove_label(self, issue_number: int, label: str) -> None:
        label_encoded = label.replace(" ", "%20")
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}/labels/{label_encoded}"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self._headers)
            if resp.status_code == 404:
                logger.debug("Label '%s' not present on issue #%s, skipping remove.", label, issue_number)
                return
            resp.raise_for_status()
            logger.info("Removed label '%s' from issue #%s", label, issue_number)

    async def get_issue_labels(self, issue_number: int) -> list[str]:
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}/labels"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            return [lbl["name"] for lbl in resp.json()]

    # ------------------------------------------------------------------
    # Assignees
    # ------------------------------------------------------------------

    async def assign_user(self, issue_number: int, username: str) -> None:
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}/assignees"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._headers, json={"assignees": [username]})
            resp.raise_for_status()
            logger.info("Assigned @%s to issue #%s", username, issue_number)

    async def unassign_user(self, issue_number: int, username: str) -> None:
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}/assignees"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self._headers, json={"assignees": [username]})
            resp.raise_for_status()
            logger.info("Unassigned @%s from issue #%s", username, issue_number)

    async def get_issue_assignees(self, issue_number: int) -> list[str]:
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            data = resp.json()
            return [a["login"] for a in data.get("assignees", [])]

    # ------------------------------------------------------------------
    # PR / Timeline detection
    # ------------------------------------------------------------------

    async def has_linked_pr(self, issue_number: int) -> bool:
        """
        Check the issue timeline for cross-referenced pull requests.
        Returns True if a PR has been opened that references this issue.
        """
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues/{issue_number}/timeline"
        headers = {**self._headers, "Accept": "application/vnd.github.mockingbird-preview+json"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            for event in resp.json():
                if event.get("event") == "cross-referenced":
                    source = event.get("source", {})
                    if source.get("type") == "issue":
                        issue = source.get("issue", {})
                        if issue.get("pull_request"):
                            return True
        return False

    # ------------------------------------------------------------------
    # Permission checks
    # ------------------------------------------------------------------

    async def get_user_permission(self, username: str) -> str:
        """Returns the user's permission level: admin, write, read, none."""
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/collaborators/{username}/permission"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers)
            if resp.status_code == 404:
                return "none"
            resp.raise_for_status()
            return resp.json().get("permission", "none")

    # ------------------------------------------------------------------
    # Issue history (first-time contributor check)
    # ------------------------------------------------------------------

    async def count_issues_by_user(self, username: str) -> int:
        """Count issues opened by this user in the repo (via search API)."""
        url = f"{GITHUB_API}/search/issues"
        query = f"repo:{self._owner}/{self._repo} type:issue author:{username}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, params={"q": query, "per_page": 1})
            resp.raise_for_status()
            return resp.json().get("total_count", 0)
