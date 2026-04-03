import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import settings
from app.dependencies import get_issue_comment_handler, get_issue_opened_handler
from app.handlers.issue_comment import IssueCommentHandler
from app.handlers.issue_opened import IssueOpenedHandler
from app.models.github import IssueCommentPayload, IssueOpenedPayload
from app.utils.signature import verify_signature

logger = logging.getLogger(__name__)
router = APIRouter()
#

@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
    issue_opened_handler: IssueOpenedHandler = Depends(get_issue_opened_handler),
    issue_comment_handler: IssueCommentHandler = Depends(get_issue_comment_handler),
):
    payload_bytes = await request.body()

    # Verify webhook signature
    if not verify_signature(payload_bytes, settings.webhook_secret, x_hub_signature_256):
        logger.warning("Invalid webhook signature received.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    try:
        payload_dict = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    action = payload_dict.get("action", "")
    logger.info("Received GitHub event: %s / action: %s", x_github_event, action)

    # Dispatch events
    if x_github_event == "issues" and action == "opened":
        parsed = IssueOpenedPayload(**payload_dict)
        await issue_opened_handler.handle(parsed)

    elif x_github_event == "issue_comment" and action == "created":
        parsed = IssueCommentPayload(**payload_dict)
        await issue_comment_handler.handle(parsed)

    # All other events are acknowledged but ignored (keeps noise low)
    return {"ok": True}
