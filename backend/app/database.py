import logging
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client, create_client
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)


class SupabaseRepository:
    """Persistence layer over the Supabase PostgREST client.

    Uses the service-role key for all server-side operations.
    Authorization is enforced at the API layer via client_id from JWT.
    """

    _client: Client | None = None

    @classmethod
    def client(cls) -> Client:
        if cls._client is None:
            settings = get_settings()
            cls._client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
        return cls._client

    # ── Reports ───────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def insert_report(
        self, client_id: str, market_topic: str, generated_report: str
    ) -> dict[str, Any]:
        row = {
            "client_id": client_id,
            "market_topic": market_topic,
            "generated_report": generated_report,
        }
        response = (
            self.client()
            .table("analysis_reports")
            .insert(row)
            .execute()
        )
        if not response.data:
            raise RuntimeError("Supabase insert returned no data")
        logger.info("Report persisted for client_id=%s", client_id)
        return response.data[0]

    def list_reports(self, client_id: str, limit: int = 20) -> list[dict[str, Any]]:
        response = (
            self.client()
            .table("analysis_reports")
            .select("id, client_id, market_topic, created_at")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def get_report(self, report_id: str, client_id: str) -> dict[str, Any] | None:
        response = (
            self.client()
            .table("analysis_reports")
            .select("*")
            .eq("id", report_id)
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        return response.data

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def create_job(self, client_id: str, market_topic: str) -> dict[str, Any]:
        row = {
            "client_id": client_id,
            "market_topic": market_topic,
            "status": "queued",
        }
        response = (
            self.client()
            .table("jobs")
            .insert(row)
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to create job")
        data = response.data[0]
        return {
            "job_id": data["id"],
            "status": data["status"],
            "market_topic": data["market_topic"],
            "report_id": data.get("report_id"),
            "error": data.get("error"),
            "created_at": data["created_at"],
        }

    def update_job_status(
        self,
        job_id: str,
        status: str,
        report_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        updates: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if report_id is not None:
            updates["report_id"] = report_id
        if error is not None:
            updates["error"] = error[:1000]  # cap error length

        self.client().table("jobs").update(updates).eq("id", job_id).execute()
        logger.info("Job %s → %s", job_id, status)

    def get_job(self, job_id: str, client_id: str) -> dict[str, Any] | None:
        response = (
            self.client()
            .table("jobs")
            .select("*")
            .eq("id", job_id)
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            return None
        data = response.data
        return {
            "job_id": data["id"],
            "status": data["status"],
            "market_topic": data["market_topic"],
            "report_id": data.get("report_id"),
            "error": data.get("error"),
            "created_at": data["created_at"],
        }

    def list_jobs(self, client_id: str, limit: int = 20) -> list[dict[str, Any]]:
        response = (
            self.client()
            .table("jobs")
            .select("*")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        result = []
        for data in (response.data or []):
            result.append({
                "job_id": data["id"],
                "status": data["status"],
                "market_topic": data["market_topic"],
                "report_id": data.get("report_id"),
                "error": data.get("error"),
                "created_at": data["created_at"],
            })
        return result

    def reset_stale_jobs(self) -> None:
        """Mark jobs stuck in 'running' for >15 mins as failed (crash recovery)."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        self.client().table("jobs").update({
            "status": "failed",
            "error": "Job timed out — server may have restarted. Please retry.",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("status", "running").lt("updated_at", cutoff).execute()

    # ── Usage / Billing ───────────────────────────────────────────────────────

    def record_usage(self, client_id: str, event_type: str = "analysis_run") -> None:
        self.client().table("usage_events").insert({
            "client_id": client_id,
            "event_type": event_type,
        }).execute()

    def get_usage_this_month(self, client_id: str) -> int:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        response = (
            self.client()
            .table("usage_events")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .eq("event_type", "analysis_run")
            .gte("created_at", month_start)
            .execute()
        )
        return response.count or 0

    # ── Share Tokens ──────────────────────────────────────────────────────────

    def create_share_token(self, report_id: str, client_id: str) -> str:
        # Upsert: one token per report (idempotent)
        try:
            existing = (
                self.client()
                .table("share_tokens")
                .select("token")
                .eq("report_id", report_id)
                .eq("client_id", client_id)
                .maybe_single()
                .execute()
            )
            if existing and existing.data:
                return existing.data["token"]
        except Exception:
            pass  # No existing token found — create a new one

        response = (
            self.client()
            .table("share_tokens")
            .insert({"report_id": report_id, "client_id": client_id})
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to create share token")
        return response.data[0]["token"]

    def get_report_by_share_token(self, token: str) -> dict[str, Any] | None:
        response = (
            self.client()
            .table("share_tokens")
            .select("report_id, expires_at")
            .eq("token", token)
            .maybe_single()
            .execute()
        )
        if not response.data:
            return None

        # Check expiry
        expires_at = response.data.get("expires_at")
        if expires_at:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                return None

        report_id = response.data["report_id"]
        report = (
            self.client()
            .table("analysis_reports")
            .select("*")
            .eq("id", report_id)
            .maybe_single()
            .execute()
        )
        return report.data
