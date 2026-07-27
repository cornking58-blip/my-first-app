from pathlib import Path


SERVER = Path("backend/server.py")
HOME = Path("frontend/app/(tabs)/index.tsx")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


server = SERVER.read_text(encoding="utf-8")
server = replace_once(
    server,
    '''try:\n    from .product_catalog import create_products_router\n    from .strict_catalog_ai import build_strict_catalog_ai_context, build_strict_direct_answer\n    from .catalog_auto_migrate import schedule_catalog_migration\nexcept ImportError:\n    from product_catalog import create_products_router\n    from strict_catalog_ai import build_strict_catalog_ai_context, build_strict_direct_answer\n    from catalog_auto_migrate import schedule_catalog_migration\n''',
    '''try:\n    from .product_catalog import create_products_router\n    from .strict_catalog_ai import build_strict_catalog_ai_context, build_strict_direct_answer\n    from .catalog_auto_migrate import schedule_catalog_migration\n    from .photo_diagnosis import analyze_photo_with_ai\nexcept ImportError:\n    from product_catalog import create_products_router\n    from strict_catalog_ai import build_strict_catalog_ai_context, build_strict_direct_answer\n    from catalog_auto_migrate import schedule_catalog_migration\n    from photo_diagnosis import analyze_photo_with_ai\n''',
    "photo diagnosis import",
)

server = replace_once(
    server,
    '''class AIMessageRequest(BaseModel):\n    content: str = Field(min_length=1, max_length=4000)\n\n\nclass AuthRequestCodeRequest(BaseModel):\n''',
    '''class AIMessageRequest(BaseModel):\n    content: str = Field(min_length=1, max_length=4000)\n\n\nclass PhotoDiagnosisRequest(BaseModel):\n    image_data_url: str = Field(min_length=100, max_length=9_000_000)\n    question: Optional[str] = Field(default=None, max_length=2000)\n\n\nclass AuthRequestCodeRequest(BaseModel):\n''',
    "photo request model",
)

server = replace_once(
    server,
    '''async def rollback_ai_usage(reservation: Tuple[str, str]) -> None:\n''',
    '''async def reserve_photo_usage(user: Dict[str, Any]) -> Tuple[str, str]:\n    plan = get_user_access_plan(user)\n    if plan == "owner":\n        return "owner", "owner"\n    if plan not in AI_USAGE_LIMITS:\n        raise HTTPException(\n            status_code=402,\n            detail="Пробный доступ завершён. Оформите bAIkov PRO за 740 ₽ в месяц.",\n        )\n\n    field = "photo_diagnostics"\n    limit = AI_USAGE_LIMITS[plan][field]\n    period_key = get_usage_period_key(user, plan)\n    usage_id = f"{user['id']}:{period_key}"\n    try:\n        usage = await db.ai_usage.find_one_and_update(\n            {\n                "_id": usage_id,\n                "$or": [\n                    {field: {"$lt": limit}},\n                    {field: {"$exists": False}},\n                ],\n            },\n            {\n                "$inc": {field: 1},\n                "$setOnInsert": {\n                    "user_id": user["id"],\n                    "period_key": period_key,\n                    "created_at": datetime.utcnow(),\n                },\n                "$set": {"updated_at": datetime.utcnow()},\n            },\n            upsert=True,\n            return_document=ReturnDocument.AFTER,\n        )\n    except DuplicateKeyError:\n        usage = None\n    if not usage:\n        raise HTTPException(\n            status_code=429,\n            detail="Лимит фотодиагностик на текущий период исчерпан.",\n        )\n    return usage_id, field\n\n\nasync def rollback_ai_usage(reservation: Tuple[str, str]) -> None:\n''',
    "photo usage reservation",
)

server = replace_once(
    server,
    '''@api_router.get("/health")\nasync def health_check():\n''',
    '''@api_router.post("/ai/photo-diagnosis")\nasync def diagnose_photo(\n    request: PhotoDiagnosisRequest,\n    current_user: Dict[str, Any] = Depends(require_current_user),\n):\n    reservation: Optional[Tuple[str, str]] = None\n    try:\n        reservation = await reserve_photo_usage(current_user)\n        answer = await analyze_photo_with_ai(\n            request.image_data_url,\n            request.question,\n        )\n        return {"answer": sanitize_ai_output(answer)}\n    except Exception:\n        if reservation:\n            await rollback_ai_usage(reservation)\n        raise\n\n\n@api_router.get("/health")\nasync def health_check():\n''',
    "photo diagnosis endpoint",
)
SERVER.write_text(server, encoding="utf-8")


home = HOME.read_text(encoding="utf-8")
home = replace_once(
    home,
    '''              <TouchableOpacity style={styles.quickAction} activeOpacity={0.8}>\n                <View style={styles.quickIcon}>\n                  <Ionicons name="camera-outline" size={22} color={colors.primaryBright} />\n                </View>\n                <Text style={styles.quickActionTitle}>Определить</Text>\n                <Text style={styles.quickActionText}>по фото</Text>\n              </TouchableOpacity>\n''',
    '''              <TouchableOpacity\n                style={styles.quickAction}\n                activeOpacity={0.8}\n                onPress={() => router.push('/photo-diagnosis')}\n              >\n                <View style={styles.quickIcon}>\n                  <Ionicons name="camera-outline" size={22} color={colors.primaryBright} />\n                </View>\n                <Text style={styles.quickActionTitle}>Определить</Text>\n                <Text style={styles.quickActionText}>по фото</Text>\n              </TouchableOpacity>\n''',
    "photo quick action",
)
HOME.write_text(home, encoding="utf-8")
