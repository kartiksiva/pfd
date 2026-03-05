from collections.abc import Callable
from typing import Union

from app.config import get_settings


class InProcessTaskRunner:
    def enqueue(self, fn: Callable[[], None]) -> None:
        # MVP default: synchronous in-process execution hook.
        fn()


class CeleryTaskRunner:
    def enqueue(self, fn: Callable[[], None]) -> None:
        # Placeholder seam for future Celery migration.
        raise NotImplementedError("Celery adapter not implemented yet.")


def get_task_runner() -> Union[InProcessTaskRunner, CeleryTaskRunner]:
    settings = get_settings()
    if settings.task_runner == "celery":
        return CeleryTaskRunner()
    return InProcessTaskRunner()
