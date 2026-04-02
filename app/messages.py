"""
All user-facing bot messages in one place.
Keep wording calm, short, and Cornucopia-native.
"""

WELCOME_FIRST_ISSUE = (
    "Thanks for opening your first issue in Cornucopia. "
    "A maintainer will review it before it can be claimed."
)

CLAIM_NOT_READY = (
    "@{username} This issue is not ready to be claimed yet. "
    "Please wait for a maintainer to mark it ready."
)

CLAIM_ALREADY_ASSIGNED = (
    "@{username} This issue is already assigned. "
    "You have been added to the waiting list and will be considered if it becomes available again."
)

CLAIM_ALREADY_ASSIGNED_NO_QUEUE = (
    "@{username} This issue is already assigned to someone else."
)

CLAIM_SUCCESS = (
    "@{username} You have been assigned to this issue. "
    "Please open a pull request within {timeout_days} days to keep the assignment."
)

READY_CONFIRMED = (
    "This issue is now marked as ready to claim. "
    "Contributors can use `/claim` to request assignment."
)

READY_PERMISSION_DENIED = (
    "@{username} Only maintainers can mark an issue ready."
)

RELEASE_SUCCESS = (
    "@{username} You have been unassigned from this issue. "
    "It is now available for others to claim."
)

RELEASE_NOT_ASSIGNED = (
    "@{username} You are not currently assigned to this issue."
)

TIMEOUT_REMINDER = (
    "@{username} A reminder: no pull request has been linked to this issue yet. "
    "The assignment will be released in {days_left} day(s) if no PR is opened."
)

TIMEOUT_RELEASED = (
    "This issue has been unassigned from @{username} as no pull request was opened within "
    "{timeout_days} days. The issue is now available again."
)

TIMEOUT_REASSIGNED = (
    "This issue has been unassigned from @{username} and reassigned to @{next_user} "
    "who was next in the waiting list."
)
