import json
import logging
import os
from datetime import datetime
from typing import Optional

from app.config import settings
from app.models.queue import ClaimEntry, ClaimStatus, IssueQueue

logger = logging.getLogger(__name__)


def _queue_key(repo_full_name: str, issue_number: int) -> str:
    return f"{repo_full_name}#{issue_number}"


class QueueRepository:
    """
    Lightweight JSON file-backed queue store.
    Replace with a proper database (SQLite, Postgres) for production scale.
    """

    def __init__(self, path: Optional[str] = None):
        self._path = path or settings.queue_storage_path
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not load queue file; starting fresh.")
        return {}

    def _save(self) -> None:
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    def _serialize_queue(self, queue: IssueQueue) -> dict:
        return queue.model_dump(mode="json")

    def _deserialize_queue(self, data: dict) -> IssueQueue:
        return IssueQueue.model_validate(data)

    def get_queue(self, repo_full_name: str, issue_number: int) -> IssueQueue:
        key = _queue_key(repo_full_name, issue_number)
        raw = self._data.get(key)
        if raw:
            return self._deserialize_queue(raw)
        return IssueQueue(issue_number=issue_number, repo_full_name=repo_full_name)

    def save_queue(self, queue: IssueQueue) -> None:
        key = _queue_key(queue.repo_full_name, queue.issue_number)
        self._data[key] = self._serialize_queue(queue)
        self._save()

    def all_queues(self) -> list[IssueQueue]:
        return [self._deserialize_queue(v) for v in self._data.values()]

    def delete_queue(self, repo_full_name: str, issue_number: int) -> None:
        key = _queue_key(repo_full_name, issue_number)
        self._data.pop(key, None)
        self._save()
