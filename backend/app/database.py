from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

# Adapter seam: swap database_url to postgres/sqlserver URL later.
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()


def _sqlite_add_column_if_missing(table_name: str, column_name: str, ddl_type: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_type}"))


def ensure_schema_compat() -> None:
    # Lightweight compatibility for evolving SQLite schema during MVP.
    if not settings.database_url.startswith("sqlite"):
        return
    _sqlite_add_column_if_missing("jobs", "context_notes", "TEXT")
    _sqlite_add_column_if_missing("jobs", "process_name", "TEXT")
    _sqlite_add_column_if_missing("jobs", "document_template", "TEXT DEFAULT 'pdd'")
    _sqlite_add_column_if_missing("jobs", "model_plan", "JSON")
    _sqlite_add_column_if_missing("jobs", "limits_applied", "JSON")
    _sqlite_add_column_if_missing("jobs", "usage_cost_estimate", "JSON")
    _sqlite_add_column_if_missing("jobs", "progress", "JSON")
    _sqlite_add_column_if_missing("jobs", "draft_pdd", "JSON")
    _sqlite_add_column_if_missing("jobs", "draft_sipoc", "JSON")
    _sqlite_add_column_if_missing("jobs", "review_notes", "JSON")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
