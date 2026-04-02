import pytest

from app.config import settings
from app.handlers.issue_opened import IssueOpenedHandler
from app.messages import WELCOME_FIRST_ISSUE
from app.services.contributor_service import ContributorService
from tests.conftest import make_issue_opened_payload, make_mock_client


@pytest.mark.asyncio
async def test_first_time_contributor_gets_welcome():
    """A FIRST_TIME_CONTRIBUTOR opening an issue should receive a welcome comment."""
    client = make_mock_client()
    contributor_service = ContributorService(client=client)
    handler = IssueOpenedHandler(client=client, contributor_service=contributor_service)

    payload = make_issue_opened_payload(
        author="newuser",
        author_association="FIRST_TIME_CONTRIBUTOR",
    )
    await handler.handle(payload)

    client.post_comment.assert_awaited_once()
    args = client.post_comment.call_args
    assert WELCOME_FIRST_ISSUE in args[0][1]


@pytest.mark.asyncio
async def test_first_timer_gets_welcome():
    """A FIRST_TIMER opening an issue should receive a welcome comment."""
    client = make_mock_client()
    contributor_service = ContributorService(client=client)
    handler = IssueOpenedHandler(client=client, contributor_service=contributor_service)

    payload = make_issue_opened_payload(
        author="brandnew",
        author_association="FIRST_TIMER",
    )
    await handler.handle(payload)

    client.post_comment.assert_awaited_once()


@pytest.mark.asyncio
async def test_maintainer_gets_no_comment():
    """A maintainer (MEMBER) opening an issue should NOT get a welcome comment."""
    client = make_mock_client()
    contributor_service = ContributorService(client=client)
    handler = IssueOpenedHandler(client=client, contributor_service=contributor_service)

    payload = make_issue_opened_payload(
        author="maintainer1",
        author_association="MEMBER",
    )
    await handler.handle(payload)

    client.post_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_gets_no_comment():
    """An OWNER opening an issue should NOT get a welcome comment."""
    client = make_mock_client()
    contributor_service = ContributorService(client=client)
    handler = IssueOpenedHandler(client=client, contributor_service=contributor_service)

    payload = make_issue_opened_payload(
        author="owneruser",
        author_association="OWNER",
    )
    await handler.handle(payload)

    client.post_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_collaborator_gets_no_comment():
    """A COLLABORATOR opening an issue should NOT get a welcome comment."""
    client = make_mock_client()
    contributor_service = ContributorService(client=client)
    handler = IssueOpenedHandler(client=client, contributor_service=contributor_service)

    payload = make_issue_opened_payload(
        author="collab1",
        author_association="COLLABORATOR",
    )
    await handler.handle(payload)

    client.post_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_needs_review_label_added_for_new_contributor():
    """needs-review label should be added when a new contributor opens an issue."""
    client = make_mock_client()
    contributor_service = ContributorService(client=client)
    handler = IssueOpenedHandler(client=client, contributor_service=contributor_service)

    payload = make_issue_opened_payload(
        author="newuser",
        author_association="FIRST_TIME_CONTRIBUTOR",
    )
    await handler.handle(payload)

    label_calls = [call[0][1] for call in client.add_label.call_args_list]
    assert settings.label_needs_review in label_calls


@pytest.mark.asyncio
async def test_returning_contributor_no_welcome_but_gets_review_label():
    """A CONTRIBUTOR (returning) should not get a welcome but should get needs-review."""
    client = make_mock_client()
    # Simulate user has 5 previous issues
    client.count_issues_by_user.return_value = 5

    contributor_service = ContributorService(client=client)
    handler = IssueOpenedHandler(client=client, contributor_service=contributor_service)

    payload = make_issue_opened_payload(
        author="returninguser",
        author_association="CONTRIBUTOR",
    )
    await handler.handle(payload)

    client.post_comment.assert_not_awaited()
    label_calls = [call[0][1] for call in client.add_label.call_args_list]
    assert settings.label_needs_review in label_calls
