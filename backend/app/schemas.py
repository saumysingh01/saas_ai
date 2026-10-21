from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class SignupResponse(BaseModel):
    user_id: str
    email: str
    message: str = "Check your email to confirm your account."


# ── Analysis (legacy, kept for backward compat) ───────────────────────────────

class AnalysisRequest(BaseModel):
    market_topic: str = Field(..., min_length=3, max_length=500)


class AnalysisResponse(BaseModel):
    report_id: UUID
    client_id: str
    market_topic: str
    generated_report: str


class ReportSummary(BaseModel):
    id: UUID
    client_id: str
    market_topic: str
    created_at: datetime


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    market_topic: str = Field(..., min_length=3, max_length=500)


class JobResponse(BaseModel):
    job_id: UUID
    status: str                        # queued | running | done | failed
    market_topic: str
    report_id: Optional[UUID] = None
    error: Optional[str] = None
    created_at: datetime


# ── Usage / Billing ───────────────────────────────────────────────────────────

class UsageResponse(BaseModel):
    reports_this_month: int
    limit: int
    plan: str
    upgrade_url: Optional[str] = None


# ── Sharing ───────────────────────────────────────────────────────────────────

class ShareResponse(BaseModel):
    share_url: str
    token: str
