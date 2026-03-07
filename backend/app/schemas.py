from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Provider(str, Enum):
    openai = "openai"
    google = "google"
    ollama = "ollama"


class ProcessingProfile(str, Enum):
    quality = "quality"
    balanced = "balanced"
    low_cost = "low_cost"


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    needs_review = "needs_review"
    completed = "completed"
    failed = "failed"
    expired = "expired"


class ErrorObject(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiEnvelope(BaseModel):
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[ErrorObject] = None


class JobCreateResponseData(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.queued
    provider: Provider
    processing_profile: ProcessingProfile
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SIPOCRowModel(BaseModel):
    supplier: str
    input: str
    process_step: str
    output: str
    customer: str


class PDDDocumentModel(BaseModel):
    purpose: str
    scope: str
    triggers: list[str]
    preconditions: list[str]
    steps: list[dict]
    roles: list[str]
    systems: list[str]
    business_rules: list[str]
    exceptions: list[str]
    outputs: list[str]
    metrics: list[str]
    risks: list[str]
