from pathlib import Path


PRODUCT_CATALOG = Path("backend/product_catalog.py")
MIGRATION = Path("backend/migrate_catalog_to_supabase.py")
AUTO_MIGRATE = Path("backend/catalog_auto_migrate.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


catalog = PRODUCT_CATALOG.read_text(encoding="utf-8")
catalog = replace_once(
    catalog,
    "logger = logging.getLogger(__name__)\n",
    '''try:\n    from .supabase_auth import build_supabase_headers, get_supabase_read_key\nexcept ImportError:\n    from supabase_auth import build_supabase_headers, get_supabase_read_key\n\nlogger = logging.getLogger(__name__)\n''',
    "catalog auth import",
)
catalog = replace_once(
    catalog,
    '''def supabase_configured() -> bool:\n    return bool(\n        (os.environ.get("SUPABASE_URL") or "").strip()\n        and (\n            (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()\n            or (os.environ.get("SUPABASE_ANON_KEY") or "").strip()\n        )\n    )\n\n\ndef _supabase_headers() -> Dict[str, str]:\n    key = (\n        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")\n        or os.environ.get("SUPABASE_ANON_KEY")\n        or ""\n    ).strip()\n    return {\n        "apikey": key,\n        "Authorization": f"Bearer {key}",\n        "Content-Type": "application/json",\n    }\n''',
    '''def supabase_configured() -> bool:\n    return bool((os.environ.get("SUPABASE_URL") or "").strip() and get_supabase_read_key())\n\n\ndef _supabase_headers() -> Dict[str, str]:\n    return build_supabase_headers(get_supabase_read_key())\n''',
    "catalog key handling",
)
PRODUCT_CATALOG.write_text(catalog, encoding="utf-8")


migration = MIGRATION.read_text(encoding="utf-8")
migration = replace_once(
    migration,
    "COLLECTIONS = {\n",
    '''try:\n    from .supabase_auth import build_supabase_headers, get_supabase_admin_key\nexcept ImportError:\n    from supabase_auth import build_supabase_headers, get_supabase_admin_key\n\nCOLLECTIONS = {\n''',
    "migration auth import",
)
migration = replace_once(
    migration,
    '''def supabase_headers() -> Dict[str, str]:\n    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()\n    if not key:\n        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")\n    return {\n        "apikey": key,\n        "Authorization": f"Bearer {key}",\n        "Content-Type": "application/json",\n        "Prefer": "resolution=merge-duplicates,return=minimal",\n    }\n''',
    '''def supabase_headers() -> Dict[str, str]:\n    key = get_supabase_admin_key()\n    if not key:\n        raise RuntimeError("SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is required")\n    return build_supabase_headers(\n        key,\n        prefer="resolution=merge-duplicates,return=minimal",\n    )\n''',
    "migration key handling",
)
MIGRATION.write_text(migration, encoding="utf-8")


auto = AUTO_MIGRATE.read_text(encoding="utf-8")
auto = replace_once(
    auto,
    "logger = logging.getLogger(__name__)\n",
    '''try:\n    from .supabase_auth import get_supabase_admin_key\nexcept ImportError:\n    from supabase_auth import get_supabase_admin_key\n\nlogger = logging.getLogger(__name__)\n''',
    "auto migration auth import",
)
auto = replace_once(
    auto,
    '''    if not (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip():\n        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")\n''',
    '''    if not get_supabase_admin_key():\n        raise RuntimeError("SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is required")\n''',
    "auto migration key check",
)
AUTO_MIGRATE.write_text(auto, encoding="utf-8")
