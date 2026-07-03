"""The processing-run notification boundary (Slice 4.1, #52).

Step 7 of the pipeline notifies the user that their upload finished (success, zero-new-events, or
failure). Real SMS (Twilio) + email (Resend) delivery is Slice 7; this slice implements only the
*seam* so the pipeline is complete and testable now:

- ``NotificationSender`` — the Protocol the pipeline depends on.
- ``LoggingNotificationSender`` — the production stub for this slice: logs the payload (no send).
- ``FakeNotificationSender`` — records payloads so tests can assert what would be sent.
- ``get_pipeline_notifier`` — factory, overridable via FastAPI ``dependency_overrides`` (mirrors
  ``app.services.notifications.email.get_email_sender`` / ``app.services.llm.gemini``).

Slice 7 swaps ``LoggingNotificationSender`` for a real sender behind the same Protocol without
touching the pipeline.
"""

import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

logger = logging.getLogger(__name__)


class NotificationOutcome(str, Enum):
    """Which of the three terminal states the run reached, so the notification wording (and later
    Slice 7's template selection) can branch without re-deriving it from counts + status."""

    SUCCESS = "success"
    NO_NEW_EVENTS = "no_new_events"
    FAILED = "failed"


@dataclass(frozen=True)
class PipelineNotification:
    """The payload for a single processing-run notification.

    Deliberately self-contained (ids + filename + human ``message``) so a real Slice 7 sender can
    build an SMS/email from it without loading anything else, and so tests can assert on it
    directly."""

    user_id: uuid.UUID
    run_id: uuid.UUID
    filename: str
    outcome: NotificationOutcome
    new_event_count: int
    message: str


class NotificationSender(Protocol):
    async def send(self, notification: PipelineNotification) -> None:
        """Deliver (or, this slice, log) a processing-run notification."""
        ...


class LoggingNotificationSender:
    """Production notifier for Slice 4.1: logs the notification instead of sending it.

    A real SMS+email sender replaces this in Slice 7 behind the same Protocol; the pipeline is
    unaffected."""

    async def send(self, notification: PipelineNotification) -> None:
        logger.info(
            "processing-run notification: run=%s user=%s outcome=%s new_events=%d file=%s :: %s",
            notification.run_id,
            notification.user_id,
            notification.outcome.value,
            notification.new_event_count,
            notification.filename,
            notification.message,
        )


class FakeNotificationSender:
    """Records notifications instead of sending them. Used in tests to assert the step-7 payload."""

    def __init__(self) -> None:
        self.sent: list[PipelineNotification] = []

    async def send(self, notification: PipelineNotification) -> None:
        self.sent.append(notification)


def get_pipeline_notifier() -> NotificationSender:
    """Return the production notifier. Overridable via ``dependency_overrides`` in tests."""
    return LoggingNotificationSender()
