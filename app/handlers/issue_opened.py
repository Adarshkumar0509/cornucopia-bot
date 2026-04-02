import logging
from typing import Optional

from app.config import settings
from app.messages import WELCOME_FIRST_ISSUE
from app.models.github import IssueOpenedPayload
from app.services.contributor_service import ContributorService
from app.services.github_client import GitHubClient

logger = logging.getLogger(__name__)


class IssueOpenedHandler:
    def __init__(
        self,
        client: Optional[GitHubClient] = None,
        contributor_service: Optional[ContributorService] = None,
    ):
        self._client = client or GitHubClient()
        self._contributor = contributor_service or ContributorService(client=self._client)

    async def handle(self, payload: IssueOpenedPayload) -> None:
        issue = payload.issue
        author_association = payload.author_association or "NONE"
        username = issue.user.login

        logger.info(
            "Issue #%s opened by @%s (association: %s)",
            issue.number,
            username,
            author_association,
        )

        # Elevated users get no automated comment
        if self._contributor.is_elevated(author_association):
            logger.debug("Skipping welcome for elevated user @%s", username)
            return

        should_welcome = await self._contributor.should_post_welcome(
            author_association, username
        )

        if should_welcome:
            await self._client.post_comment(issue.number, WELCOME_FIRST_ISSUE)
            await self._client.add_label(issue.number, settings.label_needs_review)
            await self._client.add_label(issue.number, settings.label_new_contributor)
            logger.info("Posted welcome comment on issue #%s for @%s", issue.number, username)
        else:
            # Returning contributor but not elevated: add needs-review label only
            await self._client.add_label(issue.number, settings.label_needs_review)
            logger.debug("No welcome needed for returning contributor @%s", username)
