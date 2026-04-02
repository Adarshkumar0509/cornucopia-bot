import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import settings
from app.messages import TIMEOUT_RELEASED, TIMEOUT_REASSIGNED, TIMEOUT_REMINDER
from app.models.queue import ClaimStatus
from app.repositories.queue_repository import QueueRepository
from app.services.assignment_service import AssignmentService
from app.services.github_client import GitHubClient

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(
        self,
        client: Optional[GitHubClient] = None,
        queue_repo: Optional[QueueRepository] = None,
        assignment_service: Optional[AssignmentService] = None,
    ):
        self._client = client or GitHubClient()
        self._queue_repo = queue_repo or QueueRepository()
        self._assignment = assignment_service or AssignmentService(
            client=self._client, queue_repo=self._queue_repo
        )

    async def run_daily(self) -> None:
        """Background task: runs the timeout check every day."""
        while True:
            try:
                await self.check_timeouts()
            except Exception:
                logger.exception("Error in daily timeout check.")
            await asyncio.sleep(settings.scheduler_interval_seconds)

    async def check_timeouts(self) -> None:
        """
        Iterate all open queues. For each assigned entry:
        - Send a reminder after REMINDER_AFTER_DAYS if no PR found.
        - Release after ASSIGNMENT_TIMEOUT_DAYS if no PR found.
        """
        now = datetime.now(timezone.utc)
        timeout_threshold = timedelta(days=settings.assignment_timeout_days)
        reminder_threshold = timedelta(days=settings.reminder_after_days)

        for queue in self._queue_repo.all_queues():
            assigned = queue.get_assigned()
            if not assigned or not assigned.assigned_at:
                continue

            issue_number = queue.issue_number
            username = assigned.username
            age = now - assigned.assigned_at

            # Check for linked PR before taking any action
            try:
                has_pr = await self._client.has_linked_pr(issue_number)
            except Exception:
                logger.exception("Could not check PR for issue #%s", issue_number)
                continue

            if has_pr:
                logger.debug("Issue #%s has a linked PR, skipping timeout.", issue_number)
                continue

            if age >= timeout_threshold:
                await self._do_timeout(issue_number, username)
            elif age >= reminder_threshold and not assigned.reminder_sent:
                days_left = settings.assignment_timeout_days - age.days
                await self._send_reminder(issue_number, username, days_left)
                self._assignment.mark_reminder_sent(issue_number, username)

    async def _send_reminder(
        self, issue_number: int, username: str, days_left: int
    ) -> None:
        body = TIMEOUT_REMINDER.format(username=username, days_left=days_left)
        await self._client.post_comment(issue_number, body)
        logger.info("Sent reminder to @%s on issue #%s (%d days left)", username, issue_number, days_left)

    async def _do_timeout(self, issue_number: int, username: str) -> None:
        next_user = await self._assignment.timeout_release(issue_number, username)
        if next_user:
            body = TIMEOUT_REASSIGNED.format(
                username=username,
                next_user=next_user,
                timeout_days=settings.assignment_timeout_days,
            )
        else:
            body = TIMEOUT_RELEASED.format(
                username=username,
                timeout_days=settings.assignment_timeout_days,
            )
        await self._client.post_comment(issue_number, body)
        logger.info(
            "Timed out @%s on issue #%s%s",
            username,
            issue_number,
            f", reassigned to @{next_user}" if next_user else "",
        )
