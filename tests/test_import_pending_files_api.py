"""Tests for POST /api/v1/import-pending-files (#110).

The endpoint's own logic - storage gating, file discovery, run creation, and handing off to the
scheduler's batch method - is tested here with the storage provider and scheduler overridden
(mirrors tests/test_upload_api.py); the underlying pipeline behaviour itself is already covered by
tests/test_pipeline_runner.py.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.import_pending_files import get_import_storage
from app.api.v1.upload import get_pipeline_scheduler
from app.main import app
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.user import User
from app.services.storage.base import RemoteFile
from app.services.storage.fake import FakeStorageProvider


def unique_email() -> str:
    return f"import-pending-{uuid.uuid4().hex}@example.com"


async def _register_and_login(client: AsyncClient) -> uuid.UUID:
    email = unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", data={"email": email, "password": password})
    await client.post("/api/v1/auth/login", data={"email": email, "password": password})
    me = await client.get("/api/v1/users/me")
    return uuid.UUID(me.json()["id"])


class _RecordingBatchScheduler:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def schedule(self, **kwargs: object) -> None:  # pragma: no cover - unused here
        self.calls.append(kwargs)

    async def schedule_batch(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def _override_storage(provider: FakeStorageProvider) -> None:
    app.dependency_overrides[get_import_storage] = lambda: provider


def _override_scheduler(scheduler: _RecordingBatchScheduler) -> None:
    app.dependency_overrides[get_pipeline_scheduler] = lambda: scheduler


async def test_import_pending_files_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/import-pending-files")
    assert response.status_code == 401


async def test_import_pending_files_requires_a_connected_storage_provider(
    client: AsyncClient,
) -> None:
    # No storage config saved, and get_import_storage is not overridden - exercises the real
    # dependency's gating rather than a fake.
    await _register_and_login(client)

    response = await client.post("/api/v1/import-pending-files")

    assert response.status_code == 400
    assert response.json()["detail"] == "storage_not_connected"


async def test_import_pending_files_returns_400_when_nothing_is_pending(
    client: AsyncClient,
) -> None:
    await _register_and_login(client)
    _override_storage(FakeStorageProvider())
    _override_scheduler(_RecordingBatchScheduler())

    response = await client.post("/api/v1/import-pending-files")

    assert response.status_code == 400
    assert response.json()["detail"] == "no_pending_files"


async def test_import_pending_files_creates_one_run_per_file_and_schedules_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = await _register_and_login(client)
    file_a = RemoteFile(id="a", name="chat-a.txt")
    file_b = RemoteFile(id="b", name="chat-b.txt")
    storage = FakeStorageProvider(files={file_a: b"a", file_b: b"b"})
    scheduler = _RecordingBatchScheduler()
    _override_storage(storage)
    _override_scheduler(scheduler)

    response = await client.post("/api/v1/import-pending-files")

    assert response.status_code == 202
    first_run_id = uuid.UUID(response.json()["run_id"])

    # One ProcessingRun row per pending file, both owned by this user.
    runs = list(
        (
            await db_session.scalars(
                select(ProcessingRun).where(ProcessingRun.user_id == user_id)
            )
        ).all()
    )
    assert len(runs) == 2
    filenames = {run.filename for run in runs}
    assert filenames == {"chat-a.txt", "chat-b.txt"}
    assert all(run.status == ProcessingRunStatus.PENDING for run in runs)

    # Completes onboarding the same as a manual upload does - a user who only ever imports
    # shouldn't have "Upload First File" stuck incomplete forever.
    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.onboarding_first_upload_done is True

    # The returned run_id is the first pending file's run, matching schedule_batch's first entry.
    assert len(scheduler.calls) == 1
    call = scheduler.calls[0]
    scheduled_runs = call["runs"]
    assert isinstance(scheduled_runs, list)
    assert scheduled_runs[0][0] == first_run_id
    assert [f.name for _run_id, f in scheduled_runs] == ["chat-a.txt", "chat-b.txt"]
    assert call["storage"] is storage


async def test_e2e_test_mode_bypasses_the_drive_gate_for_import(client: AsyncClient) -> None:
    """Mirrors test_upload_api.py's equivalent - under E2E_TEST_MODE the fake provider is used
    with no connected-Drive requirement."""
    from app.core.config import Settings, get_settings

    await _register_and_login(client)
    scheduler = _RecordingBatchScheduler()

    def e2e_settings() -> Settings:
        return get_settings().model_copy(update={"e2e_test_mode": True})

    app.dependency_overrides[get_settings] = e2e_settings
    _override_scheduler(scheduler)

    # get_import_storage itself isn't overridden here - E2E_TEST_MODE makes it build a fresh (empty)
    # FakeStorageProvider, so there are no pending files. That's enough to prove the Drive gate
    # (storage_not_connected) is bypassed rather than hit before file discovery even runs.
    response = await client.post("/api/v1/import-pending-files")

    assert response.status_code == 400
    assert response.json()["detail"] == "no_pending_files"
