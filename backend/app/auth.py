from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client, Client

from app.config import get_settings

bearer = HTTPBearer()

_anon_client: Client | None = None
_admin_client: Client | None = None


def get_anon_client() -> Client:
    global _anon_client
    if _anon_client is None:
        s = get_settings()
        _anon_client = create_client(s.supabase_url, s.supabase_anon_key)
    return _anon_client


def get_admin_client() -> Client:
    global _admin_client
    if _admin_client is None:
        s = get_settings()
        _admin_client = create_client(s.supabase_url, s.supabase_service_role_key)
    return _admin_client


def get_current_client(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    """Verify the Supabase JWT and return the caller's user UUID as client_id.

    Uses user.id directly — no manual client_id metadata needed.
    Every Supabase user is valid immediately after signup.
    """
    try:
        res = get_anon_client().auth.get_user(creds.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials")

    if res.user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    return str(res.user.id)
