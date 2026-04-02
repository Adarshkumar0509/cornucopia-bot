import pytest

from app.config import settings
from app.handlers.issue_comment import IssueCommentHandler
from app.messages import READY_CONFIRMED, READY_PERMISSION_DENIED
from app.services.assignment_service import AssignmentService
from app.services.permission_service import PermissionService
from tests.conftest import InMemoryQueueRepository, make_comment_payload, make_mock_client


def make_handler(client=None, queue_repo=None):
    client = client or make_mock_client()
    queue_repo = queue_repo or InMemoryQueueRepository()
    assignment = AssignmentService(client=client, queue_repo=queue_repo)
    permission = PermissionService(client=client)
    return IssueCommentHandler(
        client=client,
        assignment_service=assignment,
        permission_service=permission,
    ), client


@pytest.mark.asyncio
async def test_ready_by_maintainer_marks_issue():
    """/ready from a MEMBER should add the ready-to-claim label and confirm."""
    handler, client = make_handler()

    payload = make_comment_payload(
        comment_body="/ready",
        author="maintainer1",
        author_association="MEMBER",
    )
    await handler.handle(payload)

    label_calls = [c[0][1] for c in client.add_label.call_args_list]
    assert settings.label_ready_to_claim in label_calls

    comment = client.post_comment.call_args[0][1]
    assert "ready" in comment.lower()


@pytest.mark.asyncio
async def test_ready_by_owner_marks_issue():
    """/ready from an OWNER should work."""
    handler, client = make_handler()

    payload = make_comment_payload(
        comment_body="/ready",
        author="owneruser",
        author_association="OWNER",
    )
    await handler.handle(payload)

    label_calls = [c[0][1] for c in client.add_label.call_args_list]
    assert settings.label_ready_to_claim in label_calls


@pytest.mark.asyncio
async def test_ready_denied_for_non_maintainer():
    """/ready from a regular contributor should be rejected."""
    handler, client = make_handler()
    client.get_user_permission.return_value = "none"

    payload = make_comment_payload(
        comment_body="/ready",
        author="randomuser",
        author_association="CONTRIBUTOR",
    )
    await handler.handle(payload)

    label_calls = [c[0][1] for c in client.add_label.call_args_list]
    assert settings.label_ready_to_claim not in label_calls

    comment = client.post_comment.call_args[0][1]
    assert "only maintainers" in comment.lower()


@pytest.mark.asyncio
async def test_ready_removes_needs_review_label():
    """/ready should remove the needs-review label when marking ready."""
    handler, client = make_handler()

    payload = make_comment_payload(
        comment_body="/ready",
        author="maintainer1",
        author_association="MEMBER",
    )
    await handler.handle(payload)

    remove_calls = [c[0][1] for c in client.remove_label.call_args_list]
    assert settings.label_needs_review in remove_calls


@pytest.mark.asyncio
async def test_ready_via_api_permission_fallback():
    """/ready from CONTRIBUTOR association but with write API permission should work."""
    handler, client = make_handler()
    client.get_user_permission.return_value = "write"

    payload = make_comment_payload(
        comment_body="/ready",
        author="externalcollaborator",
        author_association="CONTRIBUTOR",
    )
    await handler.handle(payload)

    label_calls = [c[0][1] for c in client.add_label.call_args_list]
    assert settings.label_ready_to_claim in label_calls
