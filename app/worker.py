"""Celery application stub.

This module only instantiates the Celery app so that supervisord can start
a worker process (`celery -A app.worker worker`). Real pipeline tasks land
in a later slice.
"""

import os

from celery import Celery  # type: ignore[import-untyped]

REDIS_URL = os.environ["REDIS_URL"]

celery_app = Celery("organize_me", broker=REDIS_URL, backend=REDIS_URL)
