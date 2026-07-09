"""Manual file upload -> processing pipeline (Slice 4.1, #52).

``POST /api/v1/upload`` accepts a ``.txt`` / ``.zip`` / ``.csv`` export, writes it into the user's
connected Google Drive watch folder, records a ``processing_runs`` row, and kicks off the 7-step
pipeline as an **in-process background task** (no Celery - see #52's resolved decisions). The client
then navigates to the progress page (#53) to watch the run advance.

Every external collaborator is an overridable dependency (storage provider, Gemini client, notifier,
and the background scheduler) so the endpoint's own logic - gating, validation, run creation, the
onboarding flip - is unit-testable while the full pipeline behaviour is covered directly in
tests/test_pipeline_runner.py.
"""

import asyncio
import logging
import uuid
from pathlib import PurePosixPath
from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.users import current_active_user
from app.core.config import Settings, get_settings
from app.core.prompts import FACTORY_DEFAULT_PROMPT
from app.core.security import get_credential_cipher
from app.db.session import get_db, get_engine
from app.models.llm_prompt import LLMPrompt
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.user import User
from app.services.llm.gemini import GeminiClient, get_gemini_client
from app.services.notifications.pipeline import NotificationSender, get_pipeline_notifier
from app.services.pipeline.runner import run_pipeline
from app.services.storage.base import RemoteFile, StorageProvider
from app.services.storage.factory import build_storage_provider
from app.api.v1.storage_config import get_user_storage_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])

ALLOWED_EXTENSIONS = {".txt", ".zip", ".csv"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB (per #52's resolved decision)


async def get_upload_storage(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StorageProvider:
    """Resolve the storage provider for this upload.

    Under ``E2E_TEST_MODE`` the fake provider is returned unconditionally (QA has no real Drive).
    Otherwise attempts to use the user's connected Google Drive. If not available, falls back to
    ephemeral (in-memory) storage so uploads can proceed without data loss (issue #79).
    Ephemeral uploads are logged with a warning so operators are aware."""
    if settings.e2e_test_mode:
        return build_storage_provider(config=None, settings=settings, cipher=None)
    config = await get_user_storage_config(db, user.id)
    if config is None or config.oauth_access_token is None:
        # Graceful fallback to ephemeral storage instead of rejecting the upload (issue #79).
        logger.warning(
            "user %s uploading without configured Google Drive storage, using ephemeral fallback",
            user.id,
        )
        return build_storage_provider(
            config=None, settings=settings, cipher=None, fallback_to_ephemeral=True
        )
    return build_storage_provider(
        config=config, settings=settings, cipher=get_credential_cipher()
    )


class PipelineScheduler(Protocol):
    async def schedule(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        remote_file: RemoteFile,
        storage: StorageProvider,
        gemini: GeminiClient,
        notifier: NotificationSender,
        prompt_text: str,
    ) -> None:
        """Start the pipeline for a created run (in the background, not awaited to completion)."""
        ...

    async def schedule_batch(
        self,
        *,
        runs: list[tuple[uuid.UUID, RemoteFile]],
        user_id: uuid.UUID,
        storage: StorageProvider,
        gemini: GeminiClient,
        notifier: NotificationSender,
        prompt_text: str,
    ) -> None:
        """Start a batch of runs, processed one after another (not concurrently) in a single
        background task - used by the import-pending-files endpoint (#110), where files must be
        processed sequentially rather than the fire-and-forget-per-file pattern ``schedule`` uses
        for a single manual upload."""
        ...


class BackgroundPipelineScheduler:
    """Runs the pipeline as a detached asyncio task with its **own** DB session.

    The request's session closes when the HTTP response returns, so the background task can't borrow
    it - it opens a fresh session on the app engine (per #52's resolved decision). Requires Cloud Run
    "CPU always allocated" so the task keeps executing after the response is sent (human-setup note in
    the PR)."""

    async def schedule(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        remote_file: RemoteFile,
        storage: StorageProvider,
        gemini: GeminiClient,
        notifier: NotificationSender,
        prompt_text: str,
    ) -> None:
        asyncio.create_task(
            self._run(
                run_id=run_id,
                user_id=user_id,
                remote_file=remote_file,
                storage=storage,
                gemini=gemini,
                notifier=notifier,
                prompt_text=prompt_text,
            )
        )

    async def _run(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        remote_file: RemoteFile,
        storage: StorageProvider,
        gemini: GeminiClient,
        notifier: NotificationSender,
        prompt_text: str,
    ) -> None:
        session_maker = async_sessionmaker(get_engine(), expire_on_commit=False)
        try:
            async with session_maker() as session:
                run = await session.get(ProcessingRun, run_id)
                if run is None:  # pragma: no cover - the row was just committed
                    logger.error("pipeline scheduler: run %s vanished", run_id)
                    return
                await run_pipeline(
                    session,
                    run=run,
                    user_id=user_id,
                    remote_file=remote_file,
                    storage=storage,
                    gemini=gemini,
                    notifier=notifier,
                    prompt_text=prompt_text,
                )
        except Exception:  # pragma: no cover - background task must never crash silently
            logger.exception("pipeline background task failed for run %s", run_id)
        finally:
            # Release the provider's HTTP client (a fresh one is built per upload).
            await storage.aclose()

    async def schedule_batch(
        self,
        *,
        runs: list[tuple[uuid.UUID, RemoteFile]],
        user_id: uuid.UUID,
        storage: StorageProvider,
        gemini: GeminiClient,
        notifier: NotificationSender,
        prompt_text: str,
    ) -> None:
        asyncio.create_task(
            self._run_batch(
                runs=runs,
                user_id=user_id,
                storage=storage,
                gemini=gemini,
                notifier=notifier,
                prompt_text=prompt_text,
            )
        )

    async def _run_batch(
        self,
        *,
        runs: list[tuple[uuid.UUID, RemoteFile]],
        user_id: uuid.UUID,
        storage: StorageProvider,
        gemini: GeminiClient,
        notifier: NotificationSender,
        prompt_text: str,
    ) -> None:
        """Runs each file's pipeline in turn, awaiting one before starting the next - per #110's
        resolved "sequential, not parallel" decision. One shared session for the whole batch (all
        writes are sequential, so there's no concurrent-access risk); one file's unexpected failure
        doesn't stop the rest of the batch."""
        session_maker = async_sessionmaker(get_engine(), expire_on_commit=False)
        try:
            async with session_maker() as session:
                for run_id, remote_file in runs:
                    run = await session.get(ProcessingRun, run_id)
                    if run is None:  # pragma: no cover - the row was just committed
                        logger.error("pipeline scheduler: run %s vanished", run_id)
                        continue
                    try:
                        await run_pipeline(
                            session,
                            run=run,
                            user_id=user_id,
                            remote_file=remote_file,
                            storage=storage,
                            gemini=gemini,
                            notifier=notifier,
                            prompt_text=prompt_text,
                        )
                    except Exception:  # pragma: no cover - one file must not sink the whole batch
                        logger.exception("pipeline background task failed for run %s", run_id)
                        # An unhandled failure mid-pipeline can leave the shared session's
                        # transaction unusable (SQLAlchemy raises on any further use of a session
                        # after a failed flush/commit) - roll back so the next file in the batch
                        # gets a clean session instead of silently failing too.
                        await session.rollback()
        finally:
            await storage.aclose()


def get_pipeline_scheduler() -> PipelineScheduler:
    """Return the production background scheduler. Overridable in tests."""
    return BackgroundPipelineScheduler()


async def _prompt_text_for(db: AsyncSession, user_id: uuid.UUID) -> str:
    """The user's saved extraction prompt, falling back to the factory default if none is set."""
    prompt = await db.scalar(select(LLMPrompt).where(LLMPrompt.user_id == user_id))
    return prompt.prompt_text if prompt is not None else FACTORY_DEFAULT_PROMPT


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    file: UploadFile,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageProvider = Depends(get_upload_storage),
    gemini: GeminiClient = Depends(get_gemini_client),
    notifier: NotificationSender = Depends(get_pipeline_notifier),
    scheduler: PipelineScheduler = Depends(get_pipeline_scheduler),
) -> dict[str, str]:
    filename = file.filename or ""
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_file_type"
        )

    # Read at most one byte past the cap so an oversized upload is rejected without pulling the
    # whole (potentially huge) file into memory first.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="file_too_large"
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_file")

    # Write the bytes into the watch folder, then record the run so the pipeline (and #53's progress
    # page) have a row to drive.
    remote_file = await storage.upload_file(filename, content)
    run = ProcessingRun(
        user_id=user.id, filename=filename, status=ProcessingRunStatus.PENDING
    )
    db.add(run)
    # First upload completes the onboarding step; it stays true thereafter.
    user.onboarding_first_upload_done = True
    await db.commit()
    await db.refresh(run)

    prompt_text = await _prompt_text_for(db, user.id)
    await scheduler.schedule(
        run_id=run.id,
        user_id=user.id,
        remote_file=remote_file,
        storage=storage,
        gemini=gemini,
        notifier=notifier,
        prompt_text=prompt_text,
    )
    return {"run_id": str(run.id)}
