import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict

import httpx

try:
    from .migrate_catalog_to_supabase import COLLECTIONS, migrate_collection
except ImportError:
    from migrate_catalog_to_supabase import COLLECTIONS, migrate_collection

try:
    from .supabase_auth import get_supabase_admin_key
except ImportError:
    from supabase_auth import get_supabase_admin_key

logger = logging.getLogger(__name__)


def migration_requested() -> bool:
    return (os.environ.get("CATALOG_MIGRATE_ON_START") or "").strip().lower() in {"1", "true", "yes", "on"}


def migration_forced() -> bool:
    return (os.environ.get("CATALOG_MIGRATE_FORCE") or "").strip().lower() in {"1", "true", "yes", "on"}


async def migrate_catalog_to_supabase(db: Any) -> Dict[str, Dict[str, int]]:
    if not (os.environ.get("SUPABASE_URL") or "").strip():
        raise RuntimeError("SUPABASE_URL is required")
    if not get_supabase_admin_key():
        raise RuntimeError("SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is required")

    totals: Dict[str, Dict[str, int]] = {}
    async with httpx.AsyncClient(timeout=120) as client:
        for group, collection_name in COLLECTIONS.items():
            result = await migrate_collection(db, group, collection_name, client)
            totals[group] = result
            logger.info(
                "Catalog migration %s: %s products, %s applications",
                group,
                result.get("products"),
                result.get("applications"),
            )
    return totals


async def run_catalog_migration_once(db: Any) -> None:
    if not migration_requested():
        return

    state_collection = db.system_state
    state_id = "supabase_catalog_migration_v1"
    state = await state_collection.find_one({"_id": state_id})
    if state and state.get("status") == "completed" and not migration_forced():
        logger.info("Catalog migration already completed; skipping")
        return

    await state_collection.update_one(
        {"_id": state_id},
        {
            "$set": {
                "status": "running",
                "started_at": datetime.utcnow(),
                "error": None,
            }
        },
        upsert=True,
    )
    try:
        totals = await migrate_catalog_to_supabase(db)
        await state_collection.update_one(
            {"_id": state_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "totals": totals,
                    "error": None,
                }
            },
        )
        logger.info("CATALOG_MIGRATION_COMPLETED %s", totals)
    except Exception as error:
        await state_collection.update_one(
            {"_id": state_id},
            {
                "$set": {
                    "status": "failed",
                    "failed_at": datetime.utcnow(),
                    "error": f"{type(error).__name__}: {error}",
                }
            },
        )
        logger.exception("CATALOG_MIGRATION_FAILED")


def schedule_catalog_migration(db: Any) -> None:
    if migration_requested():
        asyncio.create_task(run_catalog_migration_once(db))
