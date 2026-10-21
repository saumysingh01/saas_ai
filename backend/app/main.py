import logging
import time
import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.auth import get_anon_client, get_current_client
from app.config import get_settings
from app.crew_logic import run_market_analysis_crew
from app.database import SupabaseRepository
from app.pdf_export import report_to_pdf_bytes
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    JobCreateRequest,
    JobResponse,
    ReportSummary,
    ShareResponse,
    SignupRequest,
    SignupResponse,
    UsageResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

FREE_TIER_LIMIT = 5  # reports per month on free plan

app = FastAPI(
    title="AI Market Intelligence API",
    version="2.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

repo = SupabaseRepository()


def get_repo() -> SupabaseRepository:
    return repo


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Reset any jobs stuck in 'running' from a previous crashed session."""
    try:
        await run_in_threadpool(repo.reset_stale_jobs)
        logger.info("Stale job cleanup complete.")
    except Exception as exc:
        logger.warning("Stale job cleanup failed (non-fatal): %s", exc)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env, "version": "2.0.0"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post(
    "/api/v1/auth/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
async def signup(payload: SignupRequest) -> SignupResponse:
    """Self-serve signup — any visitor can create an account."""
    try:
        res = await run_in_threadpool(
            lambda: get_anon_client().auth.sign_up({
                "email": payload.email,
                "password": payload.password,
            })
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Signup failed: {exc}") from exc

    if res.user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Signup failed — email may already be registered.",
        )

    return SignupResponse(user_id=str(res.user.id), email=res.user.email)


# ── Jobs (async analysis) ─────────────────────────────────────────────────────

@app.post(
    "/api/v1/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
)
async def create_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> JobResponse:
    """Submit a market analysis job. Returns immediately with a job_id.
    Poll GET /api/v1/jobs/{job_id} for status updates.
    """
    # Enforce free-tier limit
    usage = await run_in_threadpool(repository.get_usage_this_month, client_id)
    if usage >= FREE_TIER_LIMIT:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Free plan limit reached ({FREE_TIER_LIMIT} reports/month). "
            "Upgrade to Pro for unlimited reports.",
        )

    job = await run_in_threadpool(repository.create_job, client_id, payload.market_topic)
    background_tasks.add_task(
        _run_analysis_background,
        job["job_id"],
        client_id,
        payload.market_topic,
        repository,
    )
    logger.info("Job queued: %s for client=%s topic=%s", job["job_id"], client_id, payload.market_topic)
    return JobResponse(**job)


async def _run_analysis_background(
    job_id: str,
    client_id: str,
    market_topic: str,
    repository: SupabaseRepository,
) -> None:
    """Runs after the HTTP response is sent via FastAPI BackgroundTasks."""
    await run_in_threadpool(repository.update_job_status, job_id, "running")
    try:
        report_markdown = await run_in_threadpool(run_market_analysis_crew, market_topic)
        saved = await run_in_threadpool(
            repository.insert_report, client_id, market_topic, report_markdown
        )
        await run_in_threadpool(repository.record_usage, client_id)
        await run_in_threadpool(
            repository.update_job_status, job_id, "done", report_id=saved["id"]
        )
        logger.info("Job done: %s report_id=%s", job_id, saved["id"])
    except Exception as exc:
        logger.exception("Job failed: %s", job_id)
        await run_in_threadpool(
            repository.update_job_status, job_id, "failed", error=str(exc)
        )


@app.get(
    "/api/v1/jobs",
    response_model=list[JobResponse],
    tags=["jobs"],
)
async def list_jobs(
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> list[JobResponse]:
    """List all jobs for the authenticated user, newest first."""
    rows = await run_in_threadpool(repository.list_jobs, client_id)
    return [JobResponse(**row) for row in rows]


@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobResponse,
    tags=["jobs"],
)
async def get_job(
    job_id: str,
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> JobResponse:
    job = await run_in_threadpool(repository.get_job, job_id, client_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return JobResponse(**job)


# ── Reports ───────────────────────────────────────────────────────────────────

@app.get(
    "/api/v1/reports",
    response_model=list[ReportSummary],
    tags=["reports"],
)
async def list_reports(
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> list[ReportSummary]:
    rows = await run_in_threadpool(repository.list_reports, client_id)
    return [ReportSummary(**row) for row in rows]


@app.get(
    "/api/v1/reports/{report_id}",
    response_model=AnalysisResponse,
    tags=["reports"],
)
async def get_report(
    report_id: str,
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> AnalysisResponse:
    row = await run_in_threadpool(repository.get_report, report_id, client_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return AnalysisResponse(
        report_id=row["id"],
        client_id=row["client_id"],
        market_topic=row["market_topic"],
        generated_report=row["generated_report"],
    )


@app.get(
    "/api/v1/reports/{report_id}/pdf",
    tags=["reports"],
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_report_pdf(
    report_id: str,
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> Response:
    """Download a report as a styled PDF."""
    row = await run_in_threadpool(repository.get_report, report_id, client_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")

    pdf_bytes = await run_in_threadpool(
        report_to_pdf_bytes, row["market_topic"], row["generated_report"]
    )
    safe_name = row["market_topic"][:50].replace(" ", "_").replace("/", "-") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.post(
    "/api/v1/reports/{report_id}/share",
    response_model=ShareResponse,
    tags=["reports"],
)
async def create_share_link(
    report_id: str,
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> ShareResponse:
    """Generate a public share link for a report (no login required to view)."""
    row = await run_in_threadpool(repository.get_report, report_id, client_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")

    token = await run_in_threadpool(repository.create_share_token, report_id, client_id)
    share_url = f"{settings.app_base_url}/share.html?token={token}"
    return ShareResponse(share_url=share_url, token=token)


# ── Public Share ──────────────────────────────────────────────────────────────

@app.get("/api/v1/share/{token}", tags=["public"])
async def get_shared_report(
    token: str,
    repository: SupabaseRepository = Depends(get_repo),
) -> dict:
    """Public endpoint — no auth required. Returns the shared report."""
    row = await run_in_threadpool(repository.get_report_by_share_token, token)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share link not found or expired.")
    return {
        "market_topic": row["market_topic"],
        "generated_report": row["generated_report"],
        "created_at": row["created_at"],
    }


# ── Usage / Billing ───────────────────────────────────────────────────────────

@app.get(
    "/api/v1/usage",
    response_model=UsageResponse,
    tags=["billing"],
)
async def get_usage(
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> UsageResponse:
    count = await run_in_threadpool(repository.get_usage_this_month, client_id)
    return UsageResponse(
        reports_this_month=count,
        limit=FREE_TIER_LIMIT,
        plan="free",
        upgrade_url=None,  # drop in Stripe Payment Link here when ready
    )


# ── Legacy analysis endpoint (backward compat) ────────────────────────────────

@app.post(
    "/api/v1/analysis",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["legacy"],
    deprecated=True,
)
async def create_analysis_legacy(
    payload: AnalysisRequest,
    client_id: str = Depends(get_current_client),
    repository: SupabaseRepository = Depends(get_repo),
) -> AnalysisResponse:
    """Legacy synchronous endpoint — use POST /api/v1/jobs instead."""
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    try:
        report_markdown = await run_in_threadpool(
            run_market_analysis_crew, payload.market_topic
        )
    except Exception as exc:
        logger.exception("Crew execution failed request_id=%s", request_id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Analysis pipeline failed: {type(exc).__name__}: {exc}",
        ) from exc

    try:
        saved = await run_in_threadpool(
            repository.insert_report,
            client_id,
            payload.market_topic,
            report_markdown,
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Report generated but could not be saved.",
        ) from exc

    await run_in_threadpool(repository.record_usage, client_id)
    elapsed = time.perf_counter() - start
    logger.info("Legacy analysis done request_id=%s elapsed=%.2fs", request_id, elapsed)

    return AnalysisResponse(
        report_id=saved["id"],
        client_id=saved["client_id"],
        market_topic=saved["market_topic"],
        generated_report=saved["generated_report"],
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env == "development",
        workers=1,
    )
