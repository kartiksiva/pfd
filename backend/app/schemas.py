from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Provider(str, Enum):
    openai = "openai"
    azure_openai = "azure_openai"
    google = "google"
    ollama = "ollama"


class ProcessingProfile(str, Enum):
    quality = "quality"
    balanced = "balanced"
    low_cost = "low_cost"


class DocumentTemplate(str, Enum):
    pdd = "pdd"
    sop = "sop"


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
    document_template: DocumentTemplate = DocumentTemplate.pdd
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


class SOPDocumentModel(BaseModel):
    document_control: dict[str, Any]
    revision_history: list[dict[str, Any]]
    purpose: str
    scope: dict[str, Any]
    roles_and_responsibilities: list[dict[str, Any]]
    definitions: list[dict[str, Any]]
    prerequisites_and_inputs: dict[str, Any]
    process_overview: dict[str, Any]
    steps: list[dict[str, Any]]
    quality_checks: dict[str, Any]
    exception_handling: dict[str, Any]
    sla_and_performance_targets: list[dict[str, Any]]
    tools_and_systems_reference: list[dict[str, Any]]
    training_and_kt: dict[str, Any]
    controls_and_compliance: dict[str, Any]
    related_documents: list[dict[str, Any]]
