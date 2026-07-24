import asyncio
import os
import sys
import uuid
from collections import defaultdict
from typing import Any, Dict, Iterable, List

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from .catalog_quality import clean_catalog_product_name, should_exclude_product
except ImportError:
    from catalog_quality import clean_catalog_product_name, should_exclude_product

COLLECTIONS = {
    "herbicide": "herbicide_records",
    "fungicide": "fungicide_records",
    "insecticide": "insecticide_records",
    "seed_treatment": "seed_treatment_records",
}

MANUFACTURER_FIELDS = (
    "manufacturer",
    "registrant",
    "producer",
    "company",
    "applicant",
    "registration_holder",
    "registrant_name",
    "manufacturer_name",
    "producer_name",
    "organization",
    "registrant_organization",
    "certificate_holder",
)

NAMESPACE = uuid.UUID("8f323ce8-cfb7-4d68-b65d-374577350b61")


def batches(rows: List[Dict[str, Any]], size: int = 500) -> Iterable[List[Dict[str, Any]]]:
    for index in range(0, len(rows), size):
        yield rows[index:index + size]


def text(value: Any) -> Any:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def first_value(row: Dict[str, Any], fields) -> Any:
    for field in fields:
        value = text(row.get(field))
        if value:
            return value
    return None


def product_uuid(group: str, product_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{group}:{product_key}"))


def supabase_headers() -> Dict[str, str]:
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


async def upsert_rows(client: httpx.AsyncClient, table: str, rows: List[Dict[str, Any]], conflict: str) -> None:
    if not rows:
        return
    base_url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    if not base_url:
        raise RuntimeError("SUPABASE_URL is required")
    for batch in batches(rows):
        response = await client.post(
            f"{base_url}/rest/v1/{table}?on_conflict={conflict}",
            headers=supabase_headers(),
            json=batch,
        )
        response.raise_for_status()


async def migrate_collection(db: Any, group: str, collection_name: str, client: httpx.AsyncClient) -> Dict[str, int]:
    source_rows = await db[collection_name].find({}).to_list(length=None)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        key = text(row.get("product_key"))
        if key:
            grouped[key].append(row)

    products: List[Dict[str, Any]] = []
    applications: List[Dict[str, Any]] = []

    for product_key, rows in grouped.items():
        if should_exclude_product(group, rows):
            continue
        first = rows[0]
        pid = product_uuid(group, product_key)
        composition = next((text(row.get("active_substances_raw")) for row in rows if text(row.get("active_substances_raw"))), None)
        statuses = {text(row.get("registration_status")) for row in rows}
        registration_status = "Действует" if "Действует" in statuses else text(first.get("registration_status"))
        products.append({
            "id": pid,
            "product_group": group,
            "source_collection": collection_name,
            "source_product_key": product_key,
            "product_name": clean_catalog_product_name(first.get("product_name")),
            "formulation": text(first.get("formulation")),
            "active_substances_raw": composition,
            "manufacturer": first_value(first, MANUFACTURER_FIELDS),
            "registrant": text(first.get("registrant")),
            "producer": text(first.get("producer")),
            "company": text(first.get("company")),
            "applicant": text(first.get("applicant")),
            "registration_holder": text(first.get("registration_holder")),
            "registration_number": text(first.get("registration_number")),
            "registration_start_date": text(first.get("registration_start_date")),
            "registration_end_date": text(first.get("registration_end_date")),
            "registration_status": registration_status,
            "source_type": text(first.get("source_type")),
        })

        for index, row in enumerate(rows):
            source_record_id = text(row.get("record_id")) or text(row.get("id")) or f"{group}:{product_key}:{index}"
            applications.append({
                "product_id": pid,
                "source_record_id": source_record_id,
                "crop": text(row.get("crop")),
                "target_object": text(row.get("target_object")),
                "rate_raw": text(row.get("rate_raw")),
                "application_method": text(row.get("application_method")),
                "waiting_period": text(row.get("waiting_period")),
                "reentry_period_manual": text(row.get("reentry_period_manual")),
                "reentry_period_mech": text(row.get("reentry_period_mech")),
                "restrictions": text(row.get("restrictions")),
                "source_page": text(row.get("source_page")),
                "source_type": text(row.get("source_type")),
                "notes": text(row.get("notes")),
                "pesticide_type": text(row.get("pesticide_type")),
            })

    await upsert_rows(client, "catalog_products", products, "source_collection,source_product_key")
    await upsert_rows(client, "catalog_applications", applications, "product_id,source_record_id")
    return {
        "source_rows": len(source_rows),
        "products": len(products),
        "applications": len(applications),
    }


async def main() -> None:
    mongo_url = (os.environ.get("MONGO_URL") or "").strip()
    if not mongo_url:
        raise RuntimeError("MONGO_URL is required")
    mongo = AsyncIOMotorClient(mongo_url)
    db = mongo[os.environ.get("DB_NAME", "herbicides_db")]

    async with httpx.AsyncClient(timeout=60) as client:
        totals = {}
        for group, collection_name in COLLECTIONS.items():
            result = await migrate_collection(db, group, collection_name, client)
            totals[group] = result
            print(f"{group}: {result['products']} products, {result['applications']} applications")

    mongo.close()
    print("Migration completed")
    print(totals)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(f"Migration failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise
