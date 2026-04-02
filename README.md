# Cornucopia Bot

A GitHub bot for [OWASP Cornucopia](https://github.com/OWASP/cornucopia) that handles contributor onboarding, issue claiming, maintainer review flow, and automatic reassignment.

---

## Features

- **First-time contributor welcome** — posts one calm, short comment when a genuine new contributor opens an issue.
- **Maintainer silence** — no automated comments when a maintainer or collaborator opens an issue.
- **`/claim` command** — contributors claim issues with a strict command; first valid claim wins.
- **Waiting queue** — later claimants are queued and auto-promoted if the current assignee times out.
- **`/ready` command** — maintainers mark issues ready to claim.
- **`/release` command** — contributors voluntarily release their assignment.
- **Automatic timeout** — if no PR is opened within 15 days, the bot unassigns and moves to the next queued contributor.
- **Reminder** — a gentle reminder is sent 3 days before the timeout.
- **PR detection** — uses the GitHub timeline API; a linked PR prevents auto-release.
- **Low noise** — the bot only comments when it adds value.

---

## Architecture

```
cornucopia-bot/
├── app/
│   ├── main.py              # FastAPI app, lifespan, router registration
│   ├── config.py            # All policy values via pydantic-settings
│   ├── dependencies.py      # FastAPI dependency injection wiring
│   ├── messages.py          # All user-facing text in one place
│   ├── routes/
│   │   └── webhook.py       # POST /webhook/github — signature check + dispatch
│   ├── handlers/
│   │   ├── issue_opened.py  # issues.opened event
│   │   └── issue_comment.py # issue_comment.created — /claim, /release, /ready
│   ├── services/
│   │   ├── github_client.py     # GitHub REST API wrapper (httpx)
│   │   ├── contributor_service.py  # First-time contributor detection
│   │   ├── permission_service.py   # Maintainer / collaborator checks
│   │   ├── assignment_service.py   # Claim, release, queue management
│   │   └── scheduler.py            # Daily timeout + reminder job
│   ├── repositories/
│   │   └── queue_repository.py  # JSON file-backed issue queue store
│   ├── models/
│   │   ├── github.py   # Pydantic models for webhook payloads
│   │   └── queue.py    # ClaimEntry, IssueQueue, ClaimStatus
│   └── utils/
│       └── signature.py  # HMAC-SHA256 webhook verification
├── tests/
│   ├── conftest.py           # Fixtures, factories, in-memory queue repo
│   ├── test_issue_opened.py  # Welcome / silence logic
│   ├── test_claim_flow.py    # /claim success, rejection, FCFS
│   ├── test_timeout.py       # Timeout, reminder, reassignment
│   ├── test_ready_command.py # /ready with permission checks
│   └── test_signature.py     # Webhook signature verification
├── .env.example
├── requirements.txt
└── pyproject.toml
```

### Design principles

- **Routes** only receive requests and dispatch. No business logic.
- **Handlers** orchestrate one event. They call services, not the GitHub API directly.
- **Services** contain all business logic and are independently testable.
- **Repositories** abstract storage. Swap the JSON file store for Postgres without touching services.
- **Config** is the single source of truth for labels, timeouts, commands, and messages.

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/OWASP/cornucopia.git   # or your fork
cd cornucopia-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | Fine-grained PAT with `issues:write` and `metadata:read` |
| `WEBHOOK_SECRET` | The secret you set in the GitHub webhook config |
| `REPO_OWNER` | `OWASP` (or your fork org) |
| `REPO_NAME` | `cornucopia` |

### 3. Create labels in GitHub

Go to **Issues → Labels** in the repository and create:

- `needs maintainer review` (suggested colour: `#e4e669`)
- `ready-to-claim` (suggested colour: `#0075ca`)
- `claimed` (suggested colour: `#d4c5f9`)
- `new-contributor` (suggested colour: `#7057ff`)

### 4. Create a GitHub webhook

In the repository go to **Settings → Webhooks → Add webhook**:

- **Payload URL**: `https://your-server.example.com/webhook/github`
- **Content type**: `application/json`
- **Secret**: the same value as `WEBHOOK_SECRET` in your `.env`
- **Events**: select *Issues* and *Issue comments*

### 5. Run the bot

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For production, use a process manager such as `systemd` or run behind a reverse proxy (nginx/Caddy).

---

## Running tests

```bash
pytest
```

All tests use in-memory mocks; no real GitHub API calls are made.

---

## Commands

| Command | Who can use | Effect |
|---|---|---|
| `/claim` | Any contributor | Claim the issue if marked `ready-to-claim` |
| `/release` | Assigned contributor | Voluntarily release the assignment |
| `/ready` | Maintainers only | Mark issue as `ready-to-claim` |

---

## Timeout policy

| Setting | Default | Config key |
|---|---|---|
| Auto-release after | 15 days | `ASSIGNMENT_TIMEOUT_DAYS` |
| Reminder sent after | 12 days | `REMINDER_AFTER_DAYS` |

Both values are configurable in `.env` without code changes.

---

## Extending the bot

- **New commands**: add a branch in `IssueCommentHandler.handle()` and a new service method.
- **New events**: add a new handler class, register the event in `routes/webhook.py`.
- **Database backend**: replace `QueueRepository` with a SQLAlchemy or asyncpg implementation; the service layer is unchanged.
- **GitHub App auth**: swap `GITHUB_TOKEN` for JWT-based installation token generation in `github_client.py`.

---

## Minimum GitHub permissions

| Permission | Level | Reason |
|---|---|---|
| Issues | Read & write | Comment, label, assign |
| Metadata | Read | Repository info |
| Members | Read | Collaborator permission lookup |
