from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GitHub App / Webhook credentials
    github_token: str = ""
    webhook_secret: str = ""

    # Repository identity
    repo_owner: str = "OWASP"
    repo_name: str = "cornucopia"

    # Labels
    label_needs_review: str = "needs maintainer review"
    label_ready_to_claim: str = "ready-to-claim"
    label_claimed: str = "claimed"
    label_new_contributor: str = "new-contributor"

    # Commands (must be exact, leading slash)
    command_claim: str = "/claim"
    command_release: str = "/release"
    command_ready: str = "/ready"

    # Timeout policy (in days)
    assignment_timeout_days: int = 15
    reminder_after_days: int = 12

    # Queue storage (path for simple JSON file store)
    queue_storage_path: str = "data/queue.json"

    # Scheduler interval (seconds between daily checks)
    scheduler_interval_seconds: int = 86400  # 24 hours

    # Maintainer author associations granted elevated permissions
    elevated_author_associations: list[str] = [
        "OWNER",
        "MEMBER",
        "COLLABORATOR",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
