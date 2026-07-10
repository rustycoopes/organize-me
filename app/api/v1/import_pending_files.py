"""Import pending files -> processing pipeline (Slice 7, #110).

``POST /api/v1/import-pending-files`` scans the user's connected storage watch folder for files
not yet processed (``StorageProvider.list_new_files`` already excludes ``processed/``/``failed/``
by contract - no separate dedup bookkeeping needed), creates one ``processing_runs`` row per file,
and processes them **sequentially** - one file's pipeline run awaited before the next starts - as a
single background task (``PipelineScheduler.schedule_batch`` in ``app.api.v1.upload``). This is
unlike the manual-upload path, which fires one independent background task per upload.

The endpoint returns only the first run's id, so the client follows it to ``/processing`` exactly
like a manual upload; any further files in the batch keep processing in the background and are
visible afterward via the ``/logs`` history page rather than a second live SSE stream (#110's
chosen v1 UX - a fully "watch every file complete live" UI was considered and deferred).

Requires a connected storage provider - no ephemeral fallback like ``app.api.v1.upload``'s
``get_upload_storage``, since there's no watch folder to scan without one.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.storage_config import config_is_connected, get_user_storage_config
from app.api.v1.upload import PipelineScheduler, _prompt_text_for, get_pipeline_scheduler
from app.auth.users import current_active_user
from app.core.config import Settings, get_settings
from app.core.security import get_credential_cipher
from app.db.session import get_db
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.user import User
from app.services.llm.gemini import GeminiClient, get_gemini_client
from app.services.notifications.pipeline import NotificationSender, get_pipeline_notifier
from app.services.storage.base import StorageProvider
from app.services.storage.factory import build_storage_provider

router = APIRouter(prefix="/api/v1", tags=["import-pending-files"])


async def get_import_storage(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StorageProvider:
    """Resolve the storage provider for a scan.

    Under ``E2E_TEST_MODE`` the fake provider is returned unconditionally, same as
    ``get_upload_storage``. Otherwise requires a connected Google Drive - a 400 if not, since
    there's no ephemeral "watch folder" to scan (unlike an upload, which can proceed without one)."""
    if settings.e2e_test_mode:
        return build_storage_provider(config=None, settings=settings, cipher=None)
    config = await get_user_storage_config(db, user.id)
    if not config_is_connected(config):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="storage_not_connected"
        )
    return build_storage_provider(config=config, settings=settings, cipher=get_credential_cipher())


@router.post("/import-pending-files", status_code=status.HTTP_202_ACCEPTED)
async def import_pending_files(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageProvider = Depends(get_import_storage),
    gemini: GeminiClient = Depends(get_gemini_client),
    notifier: NotificationSender = Depends(get_pipeline_notifier),
    scheduler: PipelineScheduler = Depends(get_pipeline_scheduler),
) -> dict[str, str]:
    pending_files = await storage.list_new_files()
    if not pending_files:
        # No batch to hand off to the scheduler, so this endpoint owns closing the provider itself
        # (schedule_batch's background task closes it for us on every other path).
        await storage.aclose()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_pending_files")

    runs = [
        ProcessingRun(user_id=user.id, filename=file.name, status=ProcessingRunStatus.PENDING)
        for file in pending_files
    ]
    db.add_all(runs)
    # Completes "Upload First File" the same as a manual upload does - a user who only ever uses
    # Import (never the Upload page directly) shouldn't have that onboarding step stuck forever.
    user.onboarding_first_upload_done = True
    # get_db's sessionmaker uses expire_on_commit=False, so each run's Python-side-default id
    # (ProcessingRun.id, populated at flush) is still readable after commit - no refresh needed.
    await db.commit()

    prompt_text = await _prompt_text_for(db, user.id)
    await scheduler.schedule_batch(
        runs=list(zip((run.id for run in runs), pending_files, strict=True)),
        user_id=user.id,
        storage=storage,
        gemini=gemini,
        notifier=notifier,
        prompt_text=prompt_text,
    )
    return {"run_id": str(runs[0].id)}
