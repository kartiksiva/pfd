import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["LLM_ENABLED"] = "false"
os.environ["OWNER_ACCESS_CODE"] = "PFCD-OWNER-TEST"
os.environ["GUEST_ACCESS_CODE"] = "PFCD-GUEST-TEST"
os.environ["GUEST_ACCESS_TIMEOUT_MINUTES"] = "30"
os.environ["ACCESS_SESSION_SECRET"] = "test-session-secret"
os.environ["ACCESS_COOKIE_SECURE"] = "false"
os.environ["AUTH_ENABLED"] = "true"
_test_runtime_dir = tempfile.mkdtemp(prefix="pfcd-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_runtime_dir}/test.db"
os.environ["UPLOADS_DIR"] = f"{_test_runtime_dir}/uploads"
os.environ["EXPORTS_DIR"] = f"{_test_runtime_dir}/exports"

from app import models  # noqa: F401
from app.database import Base, engine, ensure_schema_compat

Base.metadata.create_all(bind=engine)
ensure_schema_compat()
