"""Tests for the Events dashboard page (#54)."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.upload import get_pipeline_scheduler, get_upload_storage
from app.main import app
from app.models.event import Event
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.storage_config import StorageConfig, StorageProviderType
from app.services.storage.fake import FakeStorageProvider
from app.services.user_settings import get_or_create_user_settings
from tests.test_storage_google_drive import FakeDriveOAuth2, _drive_connect


def unique_email() -> str:
    return f"dashboard-page-{uuid.uuid4().hex}@example.com"


async def _complete_onboarding(db: AsyncSession, user_id: uuid.UUID) -> None:
    settings = await get_or_create_user_settings(db, user_id)
    settings.onboarding_storage_done = True
    settings.onboarding_notifications_done = True
    settings.onboarding_first_upload_done = True
    await db.flush()


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


async def _make_run(db: AsyncSession, user_id: uuid.UUID) -> ProcessingRun:
    run = ProcessingRun(user_id=user_id, filename="chat.txt", status=ProcessingRunStatus.SUCCESS)
    db.add(run)
    await db.flush()
    return run


async def test_dashboard_redirects_anonymous_visitor_to_login(client: AsyncClient) -> None:
    response = await client.get("/dashboard")

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/login"


async def test_dashboard_shows_empty_state_with_no_events(client: AsyncClient) -> None:
    await _register_and_login(client)

    response = await client.get("/dashboard")

    assert response.status_code == 200
    assert "No events yet" in response.text


async def test_dashboard_renders_event_row_with_all_columns(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    event = Event(
        user_id=user_id,
        run_id=run.id,
        type="Medical",
        description="Dentist appointment",
        resolved_date="Saturday 6 June 2026",
        resolved_date_earliest=date(2026, 6, 6),
        raw_date_text="Saturday",
        agreed_by=["Russ Cooper", "Christine Cooper"],
    )
    db_session.add(event)
    await db_session.flush()

    response = await client.get("/dashboard")

    assert response.status_code == 200
    body = response.text
    assert "Medical" in body
    assert "Dentist appointment" in body
    assert "Saturday 6 June 2026" in body
    assert "Saturday" in body
    assert "calendar.google.com" in body
    assert "tasks.google.com" in body
    assert f"openConfirm('{event.id}')" in body
    # Agreed-by chips show initials only, with the full name available via tooltip.
    assert '<span class="badge badge-ghost mr-1" title="Russ Cooper" tabindex="0">RC</span>' in body
    assert '<span class="badge badge-ghost mr-1" title="Christine Cooper" tabindex="0">CC</span>' in body


async def test_dashboard_shows_no_date_placeholder_for_unresolved_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id,
            run_id=run.id,
            type="Other",
            description="TBC event",
            resolved_date="TBC",
            resolved_date_earliest=None,
            raw_date_text="sometime",
            agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard")

    assert response.status_code == 200
    assert "No date" in response.text


async def test_dashboard_paginates_across_multiple_pages(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    for i in range(55):
        db_session.add(
            Event(
                user_id=user_id,
                run_id=run.id,
                type="Other",
                description=f"Event {i}",
                resolved_date=f"Date {i}",
                resolved_date_earliest=date(2026, 1, 1),
                raw_date_text="x",
                agreed_by=[],
            )
        )
    await db_session.flush()

    first_page = await client.get("/dashboard")
    second_page = await client.get("/dashboard", params={"page": 2})

    assert "Page 1 of 2" in first_page.text
    assert "Next" in first_page.text
    assert "Page 2 of 2" in second_page.text
    assert "Previous" in second_page.text


async def test_dashboard_shows_total_event_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    for i in range(3):
        db_session.add(
            Event(
                user_id=user_id,
                run_id=run.id,
                type="Other",
                description=f"Event {i}",
                resolved_date=f"Date {i}",
                resolved_date_earliest=date(2026, 1, 1),
                raw_date_text="x",
                agreed_by=[],
            )
        )
    await db_session.flush()

    response = await client.get("/dashboard")

    assert "3 events total" in response.text


async def test_dashboard_redirects_out_of_range_page_to_last_valid_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    for i in range(3):
        db_session.add(
            Event(
                user_id=user_id,
                run_id=run.id,
                type="Other",
                description=f"Event {i}",
                resolved_date=f"Date {i}",
                resolved_date_earliest=date(2026, 1, 1),
                raw_date_text="x",
                agreed_by=[],
            )
        )
    await db_session.flush()

    # Only 1 page exists (3 events, 50/page); page=5 is out of range.
    response = await client.get("/dashboard", params={"page": 5})

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/dashboard?page=1"


async def test_dashboard_does_not_redirect_when_there_are_zero_events(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)

    # No events at all: an out-of-range page must not redirect (there's no valid page to redirect
    # to) - it should fall through to the normal empty-state render.
    response = await client.get("/dashboard", params={"page": 5})

    assert response.status_code == 200
    assert "No events yet" in response.text


async def test_dashboard_import_pending_files_button_disabled_without_connected_storage(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)

    response = await client.get("/dashboard")

    assert response.status_code == 200
    assert 'id="import-pending-files-btn"' in response.text
    assert "driveConnected:false" in response.text.replace(" ", "")


async def test_dashboard_import_pending_files_button_enabled_with_connected_storage(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    db_session.add(
        StorageConfig(
            user_id=user_id,
            provider=StorageProviderType.GOOGLE_DRIVE,
            folder_path="/OrganizeMe",
            oauth_access_token="ciphertext-token",
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard")

    assert response.status_code == 200
    assert "driveConnected:true" in response.text.replace(" ", "")


async def test_dashboard_shows_onboarding_checklist_for_a_new_user(
    client: AsyncClient,
) -> None:
    # A freshly-registered user has all three onboarding flags False by default.
    await _register_and_login(client)

    response = await client.get("/dashboard")

    body = response.text
    assert response.status_code == 200
    assert "Getting Started" in body
    assert 'id="onboarding-checklist"' in body
    # All three steps incomplete → each is a link to its page. Assert the full checklist anchor
    # (label + sr-only "(to do)") rather than a bare href, so the sidebar nav's own /settings,
    # /upload, /profile links can't satisfy these assertions.
    assert (
        '<a href="/settings" class="link link-primary">Connect Storage'
        '<span class="sr-only"> (to do)</span></a>'
    ) in body
    assert (
        '<a href="/settings" class="link link-primary">Set Notification Preferences'
        '<span class="sr-only"> (to do)</span></a>'
    ) in body
    assert (
        '<a href="/upload" class="link link-primary">Upload First File'
        '<span class="sr-only"> (to do)</span></a>'
    ) in body


async def test_dashboard_onboarding_checklist_marks_done_steps_and_keeps_incomplete_ones_linked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    # Complete only Connect Storage and Upload First File; leave notifications incomplete.
    settings = await get_or_create_user_settings(db_session, user_id)
    settings.onboarding_storage_done = True
    settings.onboarding_first_upload_done = True
    await db_session.flush()

    response = await client.get("/dashboard")

    body = response.text
    assert response.status_code == 200
    # Checklist still shown (one step incomplete).
    assert 'id="onboarding-checklist"' in body
    # The two done steps render struck-through with an sr-only "(done)" marker, not as links.
    assert (
        '<span class="line-through opacity-70">Connect Storage'
        '<span class="sr-only"> (done)</span></span>'
    ) in body
    assert (
        '<span class="line-through opacity-70">Upload First File'
        '<span class="sr-only"> (done)</span></span>'
    ) in body
    # The one incomplete step still renders as a link to its page (checklist-specific anchor, so
    # the sidebar nav's own /settings link can't be what satisfies this).
    assert (
        '<a href="/settings" class="link link-primary">Set Notification Preferences'
        '<span class="sr-only"> (to do)</span></a>'
    ) in body


async def test_dashboard_hides_onboarding_checklist_once_all_steps_done(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    await _complete_onboarding(db_session, user_id)

    response = await client.get("/dashboard")

    assert response.status_code == 200
    assert 'id="onboarding-checklist"' not in response.text
    assert "Getting Started" not in response.text


async def test_dashboard_hides_onboarding_checklist_after_completing_flow_through_real_endpoints(
    client: AsyncClient,
) -> None:
    """Regression test for #115: walks all three onboarding steps through their actual API
    endpoints (Drive OAuth connect, notification-prefs PATCH, file upload) rather than flipping
    the User flags directly, so a regression in any endpoint's flag-setting logic - not just in
    the dashboard's read of those flags - would be caught here."""
    await _register_and_login(client)

    # Step 1: Connect Storage, via the real Google Drive OAuth connect flow.
    await client.put(
        "/api/v1/storage-config", json={"provider": "google_drive", "folder_path": "/OrganizeMe"}
    )
    await _drive_connect(client, FakeDriveOAuth2())

    # Step 2: Set Notification Preferences, via the real profile PATCH endpoint.
    await client.patch("/api/v1/users/me", json={"notification_email": True})

    # Step 3: Upload First File, via the real upload endpoint (storage/scheduler faked).
    app.dependency_overrides[get_upload_storage] = lambda: FakeStorageProvider()

    class _RecordingScheduler:
        async def schedule(self, **kwargs: object) -> None:
            pass

    app.dependency_overrides[get_pipeline_scheduler] = lambda: _RecordingScheduler()
    try:
        await client.post(
            "/api/v1/upload",
            files={"file": ("chat.txt", b"5/30/26, 10:00 - Russ: hi", "text/plain")},
        )
    finally:
        app.dependency_overrides.pop(get_upload_storage, None)
        app.dependency_overrides.pop(get_pipeline_scheduler, None)

    response = await client.get("/dashboard")

    assert response.status_code == 200
    assert 'id="onboarding-checklist"' not in response.text
    assert "Getting Started" not in response.text


async def test_dashboard_delete_button_gated_behind_confirm_modal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id,
            run_id=run.id,
            type="Medical",
            description="Dentist",
            resolved_date="Saturday 6 June 2026",
            resolved_date_earliest=date(2026, 6, 6),
            raw_date_text="Saturday",
            agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard")

    body = response.text
    # Delete opens a confirm modal (not a direct fetch on click); the modal itself is present.
    assert 'class="modal"' in body
    assert "openConfirm(" in body
    assert "confirmDelete" in body


# --- Filters, sort, search (Slice 5.2, #55) ---------------------------------------------------


async def test_dashboard_renders_filter_controls_and_event_type_options(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Dentist",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[],
        )
    )
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="School", description="Trip",
            resolved_date="2 Jan", resolved_date_earliest=date(2026, 1, 2),
            raw_date_text="2 Jan", agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard")

    body = response.text
    assert 'id="event-filters"' in body
    assert 'name="type"' in body
    assert 'name="date_from"' in body
    assert 'name="date_to"' in body
    assert 'name="q"' in body
    assert '<option value="Medical"' in body
    assert '<option value="School"' in body


async def test_dashboard_filters_table_by_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Dentist appointment",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[],
        )
    )
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="School", description="Parents evening",
            resolved_date="2 Jan", resolved_date_earliest=date(2026, 1, 2),
            raw_date_text="2 Jan", agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard", params={"type": "School"})

    body = response.text
    assert "Parents evening" in body
    assert "Dentist appointment" not in body


async def test_dashboard_htmx_request_returns_the_dashboard_body_fragment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Dentist appointment",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard", headers={"HX-Request": "true"})

    body = response.text
    assert "Dentist appointment" in body
    # The fragment includes the filter form (its sort toggle/hidden sort field must stay in sync
    # with whatever filter/page was just requested) but excludes the surrounding page chrome.
    assert 'id="event-filters"' in body
    assert "<html" not in body
    assert "Dashboard — OrganizeMe" not in body


async def test_dashboard_shows_no_match_message_when_filters_exclude_everything(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Dentist",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard", params={"q": "no-such-event"})

    body = response.text
    assert "No events match these filters." in body
    assert "No events yet" not in body


async def test_dashboard_accepts_empty_date_filter_params(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The filter form's date inputs submit "" (not an omitted param) when left untouched -
    HTMX serializes the form as-is - so the route must treat that the same as no filter."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Dentist",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get(
        "/dashboard", params={"date_from": "", "date_to": "", "type": "", "q": ""}
    )

    assert response.status_code == 200
    assert "Dentist" in response.text


async def test_dashboard_pagination_preserves_active_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    for i in range(55):
        db_session.add(
            Event(
                user_id=user_id, run_id=run.id, type="Medical",
                description=f"Medical event {i}", resolved_date=f"Date {i}",
                resolved_date_earliest=date(2026, 1, 1), raw_date_text="x", agreed_by=[],
            )
        )
    await db_session.flush()

    response = await client.get("/dashboard", params={"type": "Medical"})

    body = response.text
    assert "type=Medical&amp;page=2" in body or "type=Medical&page=2" in body


# --- Reviewed flag + filter (#113) --------------------------------------------------------------


async def test_dashboard_renders_reviewed_checkbox_per_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    event = Event(
        user_id=user_id, run_id=run.id, type="Medical", description="Dentist",
        resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
        raw_date_text="1 Jan", agreed_by=[],
    )
    db_session.add(event)
    await db_session.flush()

    response = await client.get("/dashboard")

    body = response.text
    assert 'name="show_reviewed"' in body
    assert f"toggleReviewed('{event.id}'" in body


async def test_dashboard_hides_reviewed_events_by_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Reviewed event",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[], reviewed=True,
        )
    )
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Unreviewed event",
            resolved_date="2 Jan", resolved_date_earliest=date(2026, 1, 2),
            raw_date_text="2 Jan", agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard")

    body = response.text
    assert "Unreviewed event" in body
    assert "Reviewed event" not in body


async def test_dashboard_show_reviewed_filter_composes_with_type_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Reviewed medical",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[], reviewed=True,
        )
    )
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="School", description="Reviewed school",
            resolved_date="2 Jan", resolved_date_earliest=date(2026, 1, 2),
            raw_date_text="2 Jan", agreed_by=[], reviewed=True,
        )
    )
    await db_session.flush()

    response = await client.get(
        "/dashboard", params={"type": "Medical", "show_reviewed": "true"}
    )

    body = response.text
    assert "Reviewed medical" in body
    assert "Reviewed school" not in body


async def test_dashboard_shows_no_match_message_when_all_events_are_reviewed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Regression: a returning user whose events are all reviewed (and hidden by the default
    show_reviewed=False) must see "No events match these filters", not the first-time-user "No
    events yet" message - they aren't a new user, their events are just hidden."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Old dentist visit",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[], reviewed=True,
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard")

    body = response.text
    assert "No events match these filters." in body
    assert "No events yet" not in body


async def test_dashboard_sort_toggle_link_preserves_active_type_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Regression: the sort toggle link/hidden field live in the filter form, which must swap
    together with the table on every HTMX request - otherwise a filter applied after a sort
    toggle (or a sort toggle applied after a filter) would submit from a stale, unswapped form
    and silently drop the other setting."""
    user_id = await _register_and_login(client)
    run = await _make_run(db_session, user_id)
    db_session.add(
        Event(
            user_id=user_id, run_id=run.id, type="Medical", description="Dentist",
            resolved_date="1 Jan", resolved_date_earliest=date(2026, 1, 1),
            raw_date_text="1 Jan", agreed_by=[],
        )
    )
    await db_session.flush()

    response = await client.get("/dashboard", params={"type": "Medical"})

    body = response.text
    assert "type=Medical&amp;sort=asc" in body or "type=Medical&sort=asc" in body
