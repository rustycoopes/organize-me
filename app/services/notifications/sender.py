"""Real implementation of NotificationSender for Slice 7 (email notifications)."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.services.notifications.email import EmailSender, ResendEmailSender
from app.services.notifications.pipeline import NotificationOutcome, PipelineNotification

logger = logging.getLogger(__name__)


class RealNotificationSender:
    """Sends branded HTML email notifications after processing runs.

    Implements the NotificationSender protocol to deliver success/zero-event/failure
    notifications via email, respecting the user's notification_email preference.
    Uses Jinja2 templates for rendering branded HTML emails with inline CSS.
    """

    _jinja_env: Environment | None = None

    def __init__(self, email_sender: EmailSender | None = None) -> None:
        self.email_sender = email_sender or ResendEmailSender()
        # Lazy-initialize the Jinja2 environment once per class (cached)
        if RealNotificationSender._jinja_env is None:
            template_dir = Path(__file__).parent.parent.parent / "templates" / "emails"
            RealNotificationSender._jinja_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=True,
            )
        self.jinja_env = RealNotificationSender._jinja_env

    async def send(self, notification: PipelineNotification) -> None:
        """Send an email notification for a processing run.

        Fetches the user's email and notification_email preference, renders the
        appropriate template, and sends via email_sender if notifications are enabled.
        """
        # Get a database session to fetch the user
        async for session in get_db():
            await self._send_with_session(session, notification)
            return

    async def _send_with_session(
        self, session: AsyncSession, notification: PipelineNotification
    ) -> None:
        """Internal method that accepts a session (useful for testing)."""
        user = await session.get(User, notification.user_id)
        if user is None:
            logger.warning("User not found for notification: %s", notification.user_id)
            return

        # Respect user preference
        if not user.notification_email:
            logger.debug(
                "Skipping email notification: user %s has notification_email=False",
                notification.user_id,
            )
            return

        # Render and send the appropriate template
        try:
            if notification.outcome == NotificationOutcome.FAILED:
                await self._send_failure_email(user.email, notification)
            else:
                # SUCCESS and NO_NEW_EVENTS both use the success template
                await self._send_success_email(user.email, notification)
        except Exception:
            logger.exception(
                "Failed to send notification email to user %s", notification.user_id
            )

    async def _send_success_email(
        self, to_email: str, notification: PipelineNotification
    ) -> None:
        """Render and send a success or zero-event notification email."""
        template = self.jinja_env.get_template("success.html.j2")
        settings = get_settings()

        html = template.render(
            filename=notification.filename,
            new_event_count=notification.new_event_count,
            dashboard_url=f"{settings.base_url}/dashboard",
        )

        await self.email_sender.send(
            to=to_email,
            subject=f"OrganizeMe: {notification.filename} processed successfully",
            html=html,
        )
        logger.info(
            "Sent success email to %s for run %s", to_email, notification.run_id
        )

    async def _send_failure_email(
        self, to_email: str, notification: PipelineNotification
    ) -> None:
        """Render and send a failure notification email."""
        template = self.jinja_env.get_template("failure.html.j2")
        settings = get_settings()

        html = template.render(
            filename=notification.filename,
            error_message=notification.message,
            log_url=f"{settings.base_url}/runs/{notification.run_id}",
        )

        await self.email_sender.send(
            to=to_email,
            subject=f"OrganizeMe: {notification.filename} processing failed",
            html=html,
        )
        logger.info(
            "Sent failure email to %s for run %s", to_email, notification.run_id
        )
