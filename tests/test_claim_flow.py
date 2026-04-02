import pytest

from app.config import settings
from app.handlers.issue_comment import IssueCommentHandler
from app.messages import CLAIM_ALREADY_ASSIGNED, CLAIM_NOT_READY, CLAIM_SUCCESS
from app.services.assignment_service import AssignmentService
from app.services.permission_service import PermissionService
from tests.conftest import (
    InMemoryQueueRepository,
    make_comment_payload,
    make_mock_client,
)

READY_LABELS = [settings.label_ready_to_claim]


def make_handler(client=None, queue_repo=None):
    client = client or make_mock_client()
    queue_repo = queue_repo or InMemoryQueueRepository()
    assignment = AssignmentService(client=client, queue_repo=queue_repo)
    permission = PermissionService(client=client)
    return IssueCommentHandler(
        client=client,
        assignment_service=assignment,
        permission_service=permission,
    ), client, queue_repo


@pytest.mark.asyncio
async def test_claim_succeeds_on_ready_issue():
    """/claim on a ready, unassigned issue should assign the user."""
    handler, client, _ = make_handler()

    payload = make_comment_payload(
        comment_body="/claim",
        author="alice",
        issue_labels=READY_LABELS,
    )
    await handler.handle(payload)

    client.assign_user.assert_awaited_once_with(42, "alice")
    comment_body = client.post_comment.call_args[0][1]
    assert "alice" in comment_body
    assert str(settings.assignment_timeout_days) in comment_body


@pytest.mark.asyncio
async def test_claim_rejected_when_issue_not_ready():
    """/claim before the issue is marked ready should be rejected with an explanation."""
    handler, client, _ = make_handler()

    payload = make_comment_payload(
        comment_body="/claim",
        author="alice",
        issue_labels=[],  # no ready-to-claim label
    )
    await handler.handle(payload)

    client.assign_user.assert_not_awaited()
    comment_body = client.post_comment.call_args[0][1]
    assert "not ready" in comment_body.lower()


@pytest.mark.asyncio
async def test_first_come_first_served():
    """The first valid /claim should assign, the second should be queued."""
    queue_repo = InMemoryQueueRepository()
    client = make_mock_client()
    handler, _, _ = make_handler(client=client, queue_repo=queue_repo)

    # Alice claims first
    payload_alice = make_comment_payload(
        comment_body="/claim",
        author="alice",
        issue_labels=READY_LABELS,
    )
    await handler.handle(payload_alice)

    # Bob claims second (same handler/queue_repo instance)
    payload_bob = make_comment_payload(
        comment_body="/claim",
        author="bob",
        issue_labels=READY_LABELS,
    )
    await handler.handle(payload_bob)

    # Alice should be assigned
    assign_calls = [c[0] for c in client.assign_user.call_args_list]
    assert ("alice" in str(assign_calls[0])) or (42, "alice") in assign_calls

    # Bot should have commented twice (claim success for Alice, queue notice for Bob)
    assert client.post_comment.call_count == 2
    second_comment = client.post_comment.call_args_list[1][0][1]
    assert "already assigned" in second_comment.lower() or "waiting" in second_comment.lower()


@pytest.mark.asyncio
async def test_random_text_not_treated_as_claim():
    """'Can I work on this?' must NOT trigger assignment."""
    handler, client, _ = make_handler()

    payload = make_comment_payload(
        comment_body="Can I work on this?",
        author="alice",
        issue_labels=READY_LABELS,
    )
    await handler.handle(payload)

    client.assign_user.assert_not_awaited()
    client.post_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_with_trailing_whitespace_is_valid():
    """/claim with trailing whitespace should still work."""
    handler, client, _ = make_handler()

    payload = make_comment_payload(
        comment_body="/claim   ",
        author="alice",
        issue_labels=READY_LABELS,
    )
    await handler.handle(payload)

    client.assign_user.assert_awaited_once_with(42, "alice")


@pytest.mark.asyncio
async def test_bot_comment_is_ignored():
    """Comments from bots (ending in [bot]) should be silently ignored."""
    handler, client, _ = make_handler()

    payload = make_comment_payload(
        comment_body="/claim",
        author="dependabot[bot]",
        issue_labels=READY_LABELS,
    )
    await handler.handle(payload)

    client.assign_user.assert_not_awaited()
    client.post_comment.assert_not_awaited()
