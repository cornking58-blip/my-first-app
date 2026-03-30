from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Any
import uuid
from datetime import datetime
import pandas as pd
import io


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'herbicides_db')]

# Create the main app
app = FastAPI(title="Herbicides API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

class HerbicideRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_id: Optional[int] = None
    product_name: str
    product_key: str  # product_name + registration_number
    formulation: Optional[str] = None
    active_substances_raw: Optional[str] = None
    manufacturer: Optional[str] = None
    registration_number: Optional[str] = None
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None
    registration_status: Optional[str] = None
    rate_raw: Optional[str] = None
    crop: Optional[str] = None
    target_object: Optional[str] = None
    application_method: Optional[str] = None
    waiting_period: Optional[str] = None
    reentry_period_manual: Optional[str] = None
    reentry_period_mech: Optional[str] = None
    restrictions: Optional[str] = None
    source_page: Optional[str] = None
    source_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ImportBatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    records_imported: int
    import_date: datetime = Field(default_factory=datetime.utcnow)
    status: str = "completed"


class ProductCard(BaseModel):
    product_key: str
    product_name: str
    formulation: Optional[str] = None
    active_substances_raw: Optional[str] = None
    manufacturer: Optional[str] = None
    registration_number: Optional[str] = None
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None
    registration_status: Optional[str] = None
    applications: List[dict] = []


class CompareRequest(BaseModel):
    left_key: str
    right_key: str


class SearchResult(BaseModel):
    product_key: str
    product_name: str
    formulation: Optional[str] = None
    active_substances_raw: Optional[str] = None
    manufacturer: Optional[str] = None
    registration_status: Optional[str] = None
    applications_count: int = 0


# ==================== HELPER FUNCTIONS ====================

def clean_value(val) -> Optional[str]:
    """Clean and normalize a value from Excel"""
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    if val_str.lower() in ['nan', 'none', '']:
        return None
    return val_str


def create_product_key(product_name: str, registration_number: Optional[str]) -> str:
    """Create a unique product key from name and registration number"""
    name = (product_name or "").strip()
    reg_num = (registration_number or "").strip()
    return f"{name}|{reg_num}"


def is_active_status(status: Optional[str]) -> bool:
    """Check if a registration status is active"""
    if not status:
        return False
    status_lower = status.lower().strip()
    return status_lower == "действует"


# ==================== ENDPOINTS ====================

@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check MongoDB connection
        await db.command("ping")
        records_count = await db.herbicide_records.count_documents({})
        return {
            "status": "healthy",
            "database": "connected",
            "records_count": records_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@api_router.post("/admin/import-excel")
async def import_excel(file: UploadFile = File(...)):
    """Import herbicide data from Excel file"""
    try:
        # Read the uploaded file
        contents = await file.read()
        
        # Parse Excel
        df = pd.read_excel(io.BytesIO(contents), sheet_name='herbicides_raw', header=3)
        
        # Clear existing data
        await db.herbicide_records.delete_many({})
        
        records = []
        for idx, row in df.iterrows():
            product_name = clean_value(row.get('product_name'))
            if not product_name:
                continue
            
            registration_number = clean_value(row.get('registration_number'))
            product_key = create_product_key(product_name, registration_number)
            
            record = {
                "id": str(uuid.uuid4()),
                "record_id": int(row.get('record_id')) if pd.notna(row.get('record_id')) else None,
                "product_name": product_name,
                "product_key": product_key,
                "formulation": clean_value(row.get('formulation')),
                "active_substances_raw": clean_value(row.get('active_substances_raw')),
                "manufacturer": clean_value(row.get('manufacturer')),
                "registration_number": registration_number,
                "registration_start_date": clean_value(row.get('registration_start_date')),
                "registration_end_date": clean_value(row.get('registration_end_date')),
                "registration_status": clean_value(row.get('registration_status')),
                "rate_raw": clean_value(row.get('rate_raw')),
                "crop": clean_value(row.get('crop')),
                "target_object": clean_value(row.get('target_object')),
                "application_method": clean_value(row.get('application_method')),
                "waiting_period": clean_value(row.get('waiting_period')),
                "reentry_period_manual": clean_value(row.get('reentry_period_manual')),
                "reentry_period_mech": clean_value(row.get('reentry_period_mech')),
                "restrictions": clean_value(row.get('restrictions')),
                "source_page": clean_value(row.get('source_page')),
                "source_type": clean_value(row.get('source_type')),
                "notes": clean_value(row.get('notes')),
                "created_at": datetime.utcnow()
            }
            records.append(record)
        
        # Insert all records
        if records:
            await db.herbicide_records.insert_many(records)
        
        # Log the import
        import_batch = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "records_imported": len(records),
            "import_date": datetime.utcnow(),
            "status": "completed"
        }
        await db.import_batches.insert_one(import_batch)
        
        # Count unique products
        unique_products = await db.herbicide_records.distinct("product_key")
        
        return {
            "message": "Import successful",
            "records_imported": len(records),
            "unique_products": len(unique_products),
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/herbicides/search", response_model=List[SearchResult])
async def search_herbicides(
    q: str = Query(default="", description="Search query"),
    only_active: bool = Query(default=False, description="Show only active registrations"),
    limit: int = Query(default=50, le=200, description="Maximum results")
):
    """Search herbicides by name, crop, target, or active substances"""
    try:
        pipeline = []
        
        # Build search filter
        if q and q.strip():
            search_regex = {"$regex": q.strip(), "$options": "i"}
            pipeline.append({
                "$match": {
                    "$or": [
                        {"product_name": search_regex},
                        {"crop": search_regex},
                        {"target_object": search_regex},
                        {"active_substances_raw": search_regex},
                        {"manufacturer": search_regex}
                    ]
                }
            })
        
        # Filter for active only
        if only_active:
            pipeline.append({
                "$match": {"registration_status": "Действует"}
            })
        
        # Group by product_key to get unique products
        pipeline.extend([
            {
                "$group": {
                    "_id": "$product_key",
                    "product_name": {"$first": "$product_name"},
                    "formulation": {"$first": "$formulation"},
                    "active_substances_raw": {"$first": "$active_substances_raw"},
                    "manufacturer": {"$first": "$manufacturer"},
                    "registration_status": {"$first": "$registration_status"},
                    "applications_count": {"$sum": 1}
                }
            },
            {"$sort": {"product_name": 1}},
            {"$limit": limit}
        ])
        
        results = await db.herbicide_records.aggregate(pipeline).to_list(length=limit)
        
        return [
            SearchResult(
                product_key=r["_id"],
                product_name=r["product_name"],
                formulation=r.get("formulation"),
                active_substances_raw=r.get("active_substances_raw"),
                manufacturer=r.get("manufacturer"),
                registration_status=r.get("registration_status"),
                applications_count=r.get("applications_count", 0)
            )
            for r in results
        ]
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/herbicides/{product_key:path}", response_model=ProductCard)
async def get_herbicide(product_key: str):
    """Get a single herbicide product with all its applications"""
    try:
        # Find all records for this product
        records = await db.herbicide_records.find(
            {"product_key": product_key}
        ).to_list(length=1000)
        
        if not records:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get the first record for product info
        first_record = records[0]
        
        # Build applications list
        applications = []
        for r in records:
            app = {
                "crop": r.get("crop"),
                "target_object": r.get("target_object"),
                "rate_raw": r.get("rate_raw"),
                "application_method": r.get("application_method"),
                "waiting_period": r.get("waiting_period"),
                "reentry_period_manual": r.get("reentry_period_manual"),
                "reentry_period_mech": r.get("reentry_period_mech"),
                "restrictions": r.get("restrictions")
            }
            # Only add if has some data
            if any(v for v in app.values() if v and v != "нет данных"):
                applications.append(app)
        
        return ProductCard(
            product_key=product_key,
            product_name=first_record.get("product_name"),
            formulation=first_record.get("formulation"),
            active_substances_raw=first_record.get("active_substances_raw"),
            manufacturer=first_record.get("manufacturer"),
            registration_number=first_record.get("registration_number"),
            registration_start_date=first_record.get("registration_start_date"),
            registration_end_date=first_record.get("registration_end_date"),
            registration_status=first_record.get("registration_status"),
            applications=applications
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get herbicide failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/herbicides/compare")
async def compare_herbicides(request: CompareRequest):
    """Compare two herbicide products"""
    try:
        # Get both products
        left_records = await db.herbicide_records.find(
            {"product_key": request.left_key}
        ).to_list(length=1000)
        
        right_records = await db.herbicide_records.find(
            {"product_key": request.right_key}
        ).to_list(length=1000)
        
        if not left_records:
            raise HTTPException(status_code=404, detail="Left product not found")
        if not right_records:
            raise HTTPException(status_code=404, detail="Right product not found")
        
        def build_product_info(records):
            first = records[0]
            
            # Collect all unique crops
            crops = list(set(r.get("crop") for r in records if r.get("crop")))
            
            # Collect all unique targets
            targets = list(set(r.get("target_object") for r in records if r.get("target_object")))
            
            # Collect all rates
            rates = list(set(r.get("rate_raw") for r in records if r.get("rate_raw")))
            
            return {
                "product_key": first.get("product_key"),
                "product_name": first.get("product_name"),
                "formulation": first.get("formulation"),
                "active_substances_raw": first.get("active_substances_raw"),
                "manufacturer": first.get("manufacturer"),
                "registration_number": first.get("registration_number"),
                "registration_status": first.get("registration_status"),
                "registration_start_date": first.get("registration_start_date"),
                "registration_end_date": first.get("registration_end_date"),
                "crops": crops,
                "targets": targets,
                "rates": rates,
                "applications_count": len(records)
            }
        
        left_info = build_product_info(left_records)
        right_info = build_product_info(right_records)
        
        # Find common and unique crops
        left_crops = set(left_info["crops"])
        right_crops = set(right_info["crops"])
        
        return {
            "left": left_info,
            "right": right_info,
            "comparison": {
                "common_crops": list(left_crops & right_crops),
                "left_only_crops": list(left_crops - right_crops),
                "right_only_crops": list(right_crops - left_crops)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compare failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/stats")
async def get_stats():
    """Get database statistics"""
    try:
        total_records = await db.herbicide_records.count_documents({})
        unique_products = await db.herbicide_records.distinct("product_key")
        active_count = await db.herbicide_records.count_documents({"registration_status": "Действует"})
        
        # Get counts by status
        status_pipeline = [
            {"$group": {"_id": "$registration_status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        statuses = await db.herbicide_records.aggregate(status_pipeline).to_list(length=100)
        
        return {
            "total_records": total_records,
            "unique_products": len(unique_products),
            "active_registrations": active_count,
            "statuses": statuses
        }
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
