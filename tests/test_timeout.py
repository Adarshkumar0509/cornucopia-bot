from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.models.queue import ClaimEntry, ClaimStatus, IssueQueue
from app.services.assignment_service import AssignmentService
from app.services.scheduler import SchedulerService
from tests.conftest import InMemoryQueueRepository, make_mock_client


def _past(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _make_assigned_queue(
    issue_number: int,
    username: str,
    days_ago: int,
    waiting: list[str] | None = None,
) -> IssueQueue:
    entries = [
        ClaimEntry(
            username=username,
            claimed_at=_past(days_ago),
            assigned_at=_past(days_ago),
            status=ClaimStatus.assigned,
        )
    ]
    for w in (waiting or []):
        entries.append(
            ClaimEntry(
                username=w,
                claimed_at=_past(days_ago - 1),
                status=ClaimStatus.waiting,
            )
        )
    return IssueQueue(
        issue_number=issue_number,
        repo_full_name="OWASP/cornucopia",
        entries=entries,
    )


@pytest.mark.asyncio
async def test_timeout_releases_assignment():
    """After TIMEOUT days, the assigned user should be unassigned."""
    client = make_mock_client()
    queue_repo = InMemoryQueueRepository()

    queue = _make_assigned_queue(
        issue_number=10, username="alice", days_ago=settings.assignment_timeout_days + 1
    )
    queue_repo.save_queue(queue)

    scheduler = SchedulerService(
        client=client,
        queue_repo=queue_repo,
        assignment_service=AssignmentService(client=client, queue_repo=queue_repo),
    )
    await scheduler.check_timeouts()

    client.unassign_user.assert_awaited_once_with(10, "alice")
    client.post_comment.assert_awaited_once()
    comment = client.post_comment.call_args[0][1]
    assert "alice" in comment


@pytest.mark.asyncio
async def test_timeout_reassigns_next_in_queue():
    """After timeout, the next person in queue should be assigned."""
    client = make_mock_client()
    queue_repo = InMemoryQueueRepository()

    queue = _make_assigned_queue(
        issue_number=11,
        username="alice",
        days_ago=settings.assignment_timeout_days + 1,
        waiting=["bob"],
    )
    queue_repo.save_queue(queue)

    scheduler = SchedulerService(
        client=client,
        queue_repo=queue_repo,
        assignment_service=AssignmentService(client=client, queue_repo=queue_repo),
    )
    await scheduler.check_timeouts()

    # Alice unassigned, Bob assigned
    client.unassign_user.assert_awaited_once_with(11, "alice")
    client.assign_user.assert_awaited_once_with(11, "bob")
    comment = client.post_comment.call_args[0][1]
    assert "bob" in comment


@pytest.mark.asyncio
async def test_reminder_sent_before_timeout():
    """After REMINDER days, a reminder comment should be posted (no unassign yet)."""
    client = make_mock_client()
    queue_repo = InMemoryQueueRepository()

    queue = _make_assigned_queue(
        issue_number=12,
        username="alice",
        days_ago=settings.reminder_after_days + 1,
    )
    queue_repo.save_queue(queue)

    scheduler = SchedulerService(
        client=client,
        queue_repo=queue_repo,
        assignment_service=AssignmentService(client=client, queue_repo=queue_repo),
    )
    await scheduler.check_timeouts()

    client.unassign_user.assert_not_awaited()
    client.post_comment.assert_awaited_once()
    comment = client.post_comment.call_args[0][1]
    assert "reminder" in comment.lower() or "pull request" in comment.lower()


@pytest.mark.asyncio
async def test_reminder_not_sent_twice():
    """A reminder should only be sent once per assignment (reminder_sent flag)."""
    client = make_mock_client()
    queue_repo = InMemoryQueueRepository()

    queue = _make_assigned_queue(
        issue_number=13,
        username="alice",
        days_ago=settings.reminder_after_days + 1,
    )
    # Mark reminder already sent
    queue.entries[0].reminder_sent = True
    queue_repo.save_queue(queue)

    scheduler = SchedulerService(
        client=client,
        queue_repo=queue_repo,
        assignment_service=AssignmentService(client=client, queue_repo=queue_repo),
    )
    await scheduler.check_timeouts()

    client.post_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_timeout_if_pr_exists():
    """If a PR is linked to the issue, no timeout action should be taken."""
    client = make_mock_client()
    client.has_linked_pr = AsyncMock(return_value=True)
    queue_repo = InMemoryQueueRepository()

    queue = _make_assigned_queue(
        issue_number=14,
        username="alice",
        days_ago=settings.assignment_timeout_days + 5,
    )
    queue_repo.save_queue(queue)

    scheduler = SchedulerService(
        client=client,
        queue_repo=queue_repo,
        assignment_service=AssignmentService(client=client, queue_repo=queue_repo),
    )
    await scheduler.check_timeouts()

    client.unassign_user.assert_not_awaited()
    client.post_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_fresh_assignment_not_timed_out():
    """A recently assigned issue should not be touched."""
    client = make_mock_client()
    queue_repo = InMemoryQueueRepository()

    queue = _make_assigned_queue(
        issue_number=15, username="alice", days_ago=2
    )
    queue_repo.save_queue(queue)

    scheduler = SchedulerService(
        client=client,
        queue_repo=queue_repo,
        assignment_service=AssignmentService(client=client, queue_repo=queue_repo),
    )
    await scheduler.check_timeouts()

    client.unassign_user.assert_not_awaited()
    client.post_comment.assert_not_awaited()
