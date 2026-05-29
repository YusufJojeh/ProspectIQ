from __future__ import annotations

import logging
from queue import Queue
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_bus: dict[str, Queue[dict[str, Any]]] = {}
_lock = Lock()


def register(job_id: str) -> Queue[dict[str, Any]]:
    q: Queue[dict[str, Any]] = Queue()
    with _lock:
        _bus[job_id] = q
    return q


def unregister(job_id: str) -> None:
    with _lock:
        _bus.pop(job_id, None)


def emit(job_id: str, stage: str, progress: int, message: str) -> None:
    with _lock:
        q = _bus.get(job_id)
    if q is not None:
        q.put_nowait({"stage": stage, "progress": progress, "message": message})
