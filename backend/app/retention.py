import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal
from app.repository import list_expired_jobs, update_job_metadata, update_job_status
from app.schemas import JobStatus

_thread_started = False


def run_retention_sweep_once() -> dict:
    settings = get_settings()
    uploads_root = Path(settings.uploads_dir)
    exports_root = Path(settings.exports_dir)
    db = SessionLocal()
    scanned = 0
    expired = 0
    try:
        jobs = list_expired_jobs(db, now=datetime.utcnow())
        scanned = len(jobs)
        for job in jobs:
            shutil.rmtree(uploads_root / job.id, ignore_errors=True)
            shutil.rmtree(exports_root / job.id, ignore_errors=True)
            update_job_metadata(
                db,
                job,
                artifacts={"md": None, "json": None, "pdf": None},
                progress={"stage": "expired", "percent": 100},
            )
            ok, _ = update_job_status(db, job, JobStatus.expired.value)
            if ok:
                expired += 1
        return {"scanned": scanned, "expired": expired}
    finally:
        db.close()


def _retention_loop() -> None:
    settings = get_settings()
    interval = max(settings.retention_sweep_seconds, 30)
    while True:
        try:
            run_retention_sweep_once()
        except Exception as exc:
            # Retention should not crash the app loop.
            print(f"[retention] sweep failed: {exc}")
        time.sleep(interval)


def start_retention_scheduler() -> None:
    global _thread_started
    if _thread_started:
        return
    thread = threading.Thread(target=_retention_loop, daemon=True, name="retention-scheduler")
    thread.start()
    _thread_started = True
