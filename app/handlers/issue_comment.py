import logging
from typing import Optional

from app.config import settings
from app.messages import (
    CLAIM_ALREADY_ASSIGNED,
    CLAIM_NOT_READY,
    CLAIM_SUCCESS,
    READY_CONFIRMED,
    READY_PERMISSION_DENIED,
    RELEASE_NOT_ASSIGNED,
    RELEASE_SUCCESS,
)
from app.models.github import IssueCommentPayload
from app.services.assignment_service import AssignmentService
from app.services.github_client import GitHubClient
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class IssueCommentHandler:
    def __init__(
        self,
        client: Optional[GitHubClient] = None,
        assignment_service: Optional[AssignmentService] = None,
        permission_service: Optional[PermissionService] = None,
    ):
        self._client = client or GitHubClient()
        self._assignment = assignment_service or AssignmentService(client=self._client)
        self._permission = permission_service or PermissionService(client=self._client)

    async def handle(self, payload: IssueCommentPayload) -> None:
        comment_body = payload.comment.body.strip()
        username = payload.comment.user.login
        author_association = payload.comment.author_association
        issue = payload.issue
        issue_number = issue.number

        # Ignore bot's own comments to avoid loops
        if username.endswith("[bot]") or username.lower().endswith("-bot"):
            return

        # Route to the right command handler
        first_line = comment_body.splitlines()[0].strip() if comment_body else ""

        if first_line == settings.command_claim:
            await self._handle_claim(issue_number, issue, username)

        elif first_line == settings.command_release:
            await self._handle_release(issue_number, username)

        elif first_line == settings.command_ready:
            await self._handle_ready(issue_number, username, author_association)

    # ------------------------------------------------------------------
    # /claim
    # ------------------------------------------------------------------

    async def _handle_claim(self, issue_number: int, issue, username: str) -> None:
        labels = [lbl.name for lbl in issue.labels]

        if settings.label_ready_to_claim not in labels:
            body = CLAIM_NOT_READY.format(username=username)
            await self._client.post_comment(issue_number, body)
            logger.info("/claim rejected (not ready) for @%s on #%s", username, issue_number)
            return

        outcome, success = await self._assignment.claim_issue(issue_number, username)

        if outcome == "assigned":
            body = CLAIM_SUCCESS.format(
                username=username,
                timeout_days=settings.assignment_timeout_days,
            )
            await self._client.post_comment(issue_number, body)
            logger.info("/claim success: @%s assigned to #%s", username, issue_number)

        elif outcome == "queued":
            body = CLAIM_ALREADY_ASSIGNED.format(username=username)
            await self._client.post_comment(issue_number, body)
            logger.info("/claim queued: @%s added to waitlist on #%s", username, issue_number)

        elif outcome == "duplicate":
            # User already in queue - quietly ignore to reduce noise
            logger.debug("/claim duplicate ignored for @%s on #%s", username, issue_number)

    # ------------------------------------------------------------------
    # /release
    # ------------------------------------------------------------------

    async def _handle_release(self, issue_number: int, username: str) -> None:
        released = await self._assignment.release_issue(issue_number, username)
        if released:
            body = RELEASE_SUCCESS.format(username=username)
            await self._client.post_comment(issue_number, body)
            logger.info("/release: @%s released #%s", username, issue_number)
        else:
            body = RELEASE_NOT_ASSIGNED.format(username=username)
            await self._client.post_comment(issue_number, body)

    # ------------------------------------------------------------------
    # /ready
    # ------------------------------------------------------------------

    async def _handle_ready(
        self,
        issue_number: int,
        username: str,
        author_association: str,
    ) -> None:
        is_maintainer = await self._permission.is_maintainer(username, author_association)

        if not is_maintainer:
            body = READY_PERMISSION_DENIED.format(username=username)
            await self._client.post_comment(issue_number, body)
            logger.info("/ready denied for @%s on #%s (not a maintainer)", username, issue_number)
            return

        await self._client.add_label(issue_number, settings.label_ready_to_claim)
        await self._client.remove_label(issue_number, settings.label_needs_review)
        await self._client.post_comment(issue_number, READY_CONFIRMED)
        logger.info("/ready applied to #%s by @%s", issue_number, username)
