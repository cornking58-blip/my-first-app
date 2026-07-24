import os
from typing import Dict, Optional


def get_supabase_read_key() -> str:
    return (
        os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    ).strip()


def get_supabase_admin_key() -> str:
    return (
        os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()


def build_supabase_headers(
    key: str,
    *,
    prefer: Optional[str] = None,
) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    if key and not key.startswith(("sb_secret_", "sb_publishable_")):
        headers["Authorization"] = f"Bearer {key}"
    if prefer:
        headers["Prefer"] = prefer
    return headers
