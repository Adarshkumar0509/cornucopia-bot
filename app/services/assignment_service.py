import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.models.queue import ClaimEntry, ClaimStatus, IssueQueue
from app.repositories.queue_repository import QueueRepository
from app.services.github_client import GitHubClient

logger = logging.getLogger(__name__)


class AssignmentService:
    def __init__(
        self,
        client: Optional[GitHubClient] = None,
        queue_repo: Optional[QueueRepository] = None,
    ):
        self._client = client or GitHubClient()
        self._queue_repo = queue_repo or QueueRepository()

    def _repo_full(self) -> str:
        return f"{settings.repo_owner}/{settings.repo_name}"

    async def claim_issue(
        self,
        issue_number: int,
        username: str,
    ) -> tuple[str, bool]:
        """
        Attempt to claim an issue.
        Returns (outcome, success) where outcome is:
          'assigned'  - successfully assigned
          'queued'    - added to waiting queue
          'duplicate' - user already in queue for this issue
        """
        queue = self._queue_repo.get_queue(self._repo_full(), issue_number)

        # Check if user is already in queue (any status)
        existing = next((e for e in queue.entries if e.username == username), None)
        if existing and existing.status in (ClaimStatus.assigned, ClaimStatus.waiting):
            return "duplicate", False

        if not queue.is_assigned():
            entry = ClaimEntry(
                username=username,
                claimed_at=datetime.now(timezone.utc),
                assigned_at=datetime.now(timezone.utc),
                status=ClaimStatus.assigned,
            )
            queue.entries.append(entry)
            self._queue_repo.save_queue(queue)
            await self._client.assign_user(issue_number, username)
            await self._client.add_label(issue_number, settings.label_claimed)
            return "assigned", True
        else:
            entry = ClaimEntry(
                username=username,
                claimed_at=datetime.now(timezone.utc),
                status=ClaimStatus.waiting,
            )
            queue.entries.append(entry)
            self._queue_repo.save_queue(queue)
            return "queued", False

    async def release_issue(
        self,
        issue_number: int,
        username: str,
    ) -> bool:
        """
        Manually release an issue. Returns True if the user was assigned.
        """
        queue = self._queue_repo.get_queue(self._repo_full(), issue_number)
        assigned = queue.get_assigned()
        if not assigned or assigned.username != username:
            return False

        assigned.status = ClaimStatus.released
        self._queue_repo.save_queue(queue)
        await self._client.unassign_user(issue_number, username)
        await self._apply_next_or_clear(issue_number, queue)
        return True

    async def _apply_next_or_clear(
        self,
        issue_number: int,
        queue: IssueQueue,
    ) -> Optional[str]:
        """Assign the next waiting person if any, otherwise clean up labels."""
        next_entry = queue.get_next_waiting()
        if next_entry:
            next_entry.status = ClaimStatus.assigned
            next_entry.assigned_at = datetime.now(timezone.utc)
            self._queue_repo.save_queue(queue)
            await self._client.assign_user(issue_number, next_entry.username)
            return next_entry.username
        else:
            await self._client.remove_label(issue_number, settings.label_claimed)
            return None

    async def timeout_release(
        self,
        issue_number: int,
        username: str,
    ) -> Optional[str]:
        """
        Release after timeout. Returns the next assignee username if any.
        """
        queue = self._queue_repo.get_queue(self._repo_full(), issue_number)
        assigned = queue.get_assigned()
        if not assigned or assigned.username != username:
            return None

        assigned.status = ClaimStatus.timed_out
        self._queue_repo.save_queue(queue)
        await self._client.unassign_user(issue_number, username)
        return await self._apply_next_or_clear(issue_number, queue)

    def mark_reminder_sent(self, issue_number: int, username: str) -> None:
        queue = self._queue_repo.get_queue(self._repo_full(), issue_number)
        assigned = queue.get_assigned()
        if assigned and assigned.username == username:
            assigned.reminder_sent = True
            self._queue_repo.save_queue(queue)
