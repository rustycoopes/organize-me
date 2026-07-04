"""Tests for Slice 7.1: branded email notifications."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.notifications.email import FakeEmailSender
from app.services.notifications.pipeline import (
    NotificationOutcome,
    PipelineNotification,
)
from app.services.notifications.sender import RealNotificationSender


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user with notifications enabled."""
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        is_active=True,
        notification_email=True,
        notification_sms=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_notifications_disabled(db_session: AsyncSession) -> User:
    """Create a test user with email notifications disabled."""
    user = User(
        email="notified@example.com",
        hashed_password="hashed",
        is_active=True,
        notification_email=False,
        notification_sms=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def fake_email_sender() -> FakeEmailSender:
    return FakeEmailSender()


class TestEmailNotifications:
    async def test_success_notification_sends_email(
        self, test_user: User, fake_email_sender: FakeEmailSender, db_session: AsyncSession
    ) -> None:
        """Test that a successful run triggers a success email."""
        sender = RealNotificationSender(email_sender=fake_email_sender)
        notification = PipelineNotification(
            user_id=test_user.id,
            run_id=uuid.uuid4(),
            filename="test.csv",
            outcome=NotificationOutcome.SUCCESS,
            new_event_count=42,
            message="42 new events added.",
        )

        await sender._send_with_session(db_session, notification)

        assert len(fake_email_sender.sent) == 1
        email = fake_email_sender.sent[0]
        assert email["to"] == test_user.email
        assert "test.csv" in email["subject"]
        assert "successfully" in email["subject"].lower()
        assert "42" in email["html"]
        assert "dashboard" in email["html"].lower()

    async def test_zero_event_notification_sends_email(
        self, test_user: User, fake_email_sender: FakeEmailSender, db_session: AsyncSession
    ) -> None:
        """Test that a zero-event run triggers a success email with count = 0."""
        sender = RealNotificationSender(email_sender=fake_email_sender)
        notification = PipelineNotification(
            user_id=test_user.id,
            run_id=uuid.uuid4(),
            filename="empty.csv",
            outcome=NotificationOutcome.NO_NEW_EVENTS,
            new_event_count=0,
            message="No new events found.",
        )

        await sender._send_with_session(db_session, notification)

        assert len(fake_email_sender.sent) == 1
        email = fake_email_sender.sent[0]
        assert email["to"] == test_user.email
        assert "empty.csv" in email["subject"]
        assert "0" in email["html"]

    async def test_failure_notification_sends_email(
        self, test_user: User, fake_email_sender: FakeEmailSender, db_session: AsyncSession
    ) -> None:
        """Test that a failed run triggers a failure email with error details."""
        sender = RealNotificationSender(email_sender=fake_email_sender)
        run_id = uuid.uuid4()
        error_message = "CSV parsing failed: invalid format"
        notification = PipelineNotification(
            user_id=test_user.id,
            run_id=run_id,
            filename="corrupt.csv",
            outcome=NotificationOutcome.FAILED,
            new_event_count=0,
            message=error_message,
        )

        await sender._send_with_session(db_session, notification)

        assert len(fake_email_sender.sent) == 1
        email = fake_email_sender.sent[0]
        assert email["to"] == test_user.email
        assert "corrupt.csv" in email["subject"]
        assert "failed" in email["subject"].lower()
        assert error_message in email["html"]
        assert str(run_id) in email["html"]

    async def test_no_email_sent_when_notifications_disabled(
        self, test_user_notifications_disabled: User, fake_email_sender: FakeEmailSender, db_session: AsyncSession
    ) -> None:
        """Test that no email is sent when user.notification_email is False."""
        sender = RealNotificationSender(email_sender=fake_email_sender)
        notification = PipelineNotification(
            user_id=test_user_notifications_disabled.id,
            run_id=uuid.uuid4(),
            filename="test.csv",
            outcome=NotificationOutcome.SUCCESS,
            new_event_count=5,
            message="5 new events added.",
        )

        await sender._send_with_session(db_session, notification)

        assert len(fake_email_sender.sent) == 0

    async def test_no_email_sent_for_unknown_user(
        self, fake_email_sender: FakeEmailSender, db_session: AsyncSession
    ) -> None:
        """Test that sending fails gracefully for unknown users."""
        sender = RealNotificationSender(email_sender=fake_email_sender)
        notification = PipelineNotification(
            user_id=uuid.uuid4(),  # Non-existent user
            run_id=uuid.uuid4(),
            filename="test.csv",
            outcome=NotificationOutcome.SUCCESS,
            new_event_count=1,
            message="1 new event added.",
        )

        # Should not raise, just log and return
        await sender._send_with_session(db_session, notification)

        assert len(fake_email_sender.sent) == 0

    async def test_success_email_contains_dashboard_link(
        self, test_user: User, fake_email_sender: FakeEmailSender, db_session: AsyncSession
    ) -> None:
        """Test that success emails contain a link to the dashboard."""
        sender = RealNotificationSender(email_sender=fake_email_sender)
        notification = PipelineNotification(
            user_id=test_user.id,
            run_id=uuid.uuid4(),
            filename="events.csv",
            outcome=NotificationOutcome.SUCCESS,
            new_event_count=10,
            message="10 new events added.",
        )

        await sender._send_with_session(db_session, notification)

        email = fake_email_sender.sent[0]
        assert "/dashboard" in email["html"]

    async def test_failure_email_contains_log_page_link(
        self, test_user: User, fake_email_sender: FakeEmailSender, db_session: AsyncSession
    ) -> None:
        """Test that failure emails contain a link to the processing log page."""
        sender = RealNotificationSender(email_sender=fake_email_sender)
        run_id = uuid.uuid4()
        notification = PipelineNotification(
            user_id=test_user.id,
            run_id=run_id,
            filename="failed.csv",
            outcome=NotificationOutcome.FAILED,
            new_event_count=0,
            message="Processing error",
        )

        await sender._send_with_session(db_session, notification)

        email = fake_email_sender.sent[0]
        assert f"/runs/{run_id}" in email["html"]
