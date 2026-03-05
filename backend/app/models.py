from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    context_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_plan: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_manifest: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    limits_applied: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    usage_cost_estimate: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    draft_pdd: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    draft_sipoc: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    review_notes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifacts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
