import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["LLM_ENABLED"] = "false"

from app import models  # noqa: F401
from app.database import Base, engine, ensure_schema_compat

Base.metadata.create_all(bind=engine)
ensure_schema_compat()
