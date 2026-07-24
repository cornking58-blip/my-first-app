from pathlib import Path


SERVER = Path("backend/server.py")
CATALOG = Path("backend/product_catalog.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


server = SERVER.read_text(encoding="utf-8")
server = replace_once(
    server,
    '''try:
    from .product_catalog import build_catalog_ai_context, build_direct_catalog_answer, create_products_router
except ImportError:
    from product_catalog import build_catalog_ai_context, build_direct_catalog_answer, create_products_router
''',
    '''try:
    from .product_catalog import create_products_router
    from .strict_catalog_ai import build_strict_catalog_ai_context, build_strict_direct_answer
    from .catalog_auto_migrate import schedule_catalog_migration
except ImportError:
    from product_catalog import create_products_router
    from strict_catalog_ai import build_strict_catalog_ai_context, build_strict_direct_answer
    from catalog_auto_migrate import schedule_catalog_migration
''',
    "server catalog imports",
)
server = replace_once(
    server,
    '''def should_force_product_web_search(message: str, context: Dict[str, Any]) -> bool:
    return is_product_specific_question(message) and not context_has_verified_product_data(context)
''',
    '''def should_force_product_web_search(message: str, context: Dict[str, Any]) -> bool:
    if context.get("allow_web_fallback") is False:
        return False
    return is_product_specific_question(message) and not context_has_verified_product_data(context)
''',
    "web fallback guard",
)
server = replace_once(
    server,
    '''async def build_general_ai_context(message: str) -> Dict[str, Any]:
    return await build_catalog_ai_context(db, message)
''',
    '''async def build_general_ai_context(message: str) -> Dict[str, Any]:
    return await build_strict_catalog_ai_context(db, message)
''',
    "strict context",
)
server = replace_once(
    server,
    '''            direct_answer = build_direct_catalog_answer(context)
''',
    '''            direct_answer = build_strict_direct_answer(context)
''',
    "strict direct answer",
)
server = replace_once(
    server,
    '''    await db.ai_usage.create_index([("user_id", 1), ("period_key", 1)], unique=True)
''',
    '''    await db.ai_usage.create_index([("user_id", 1), ("period_key", 1)], unique=True)
    schedule_catalog_migration(db)
''',
    "catalog migration startup",
)
SERVER.write_text(server, encoding="utf-8")


catalog = CATALOG.read_text(encoding="utf-8")
catalog = replace_once(
    catalog,
    '''async def search_catalog_products(
    db: Any,
    query: str = "",
    group: str = "",
    manufacturer: str = "",
    culture: str = "",
    harmful_object: str = "",
    only_active: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    if supabase_configured():
        try:
            return await search_supabase_products(
                query=query,
                group=group,
                manufacturer=manufacturer,
                culture=culture,
                harmful_object=harmful_object,
                only_active=only_active,
                limit=limit,
            )
        except Exception as error:
            logger.warning("Supabase catalog search failed, using MongoDB fallback: %s", type(error).__name__)
    return await search_mongo_products(
        db,
        query=query,
        group=group,
        manufacturer=manufacturer,
        culture=culture,
        harmful_object=harmful_object,
        only_active=only_active,
        limit=limit,
    )
''',
    '''def catalog_backend_mode() -> str:
    value = (os.environ.get("CATALOG_BACKEND") or "").strip().lower()
    if value in {"supabase", "mongo", "auto"}:
        return value
    return "supabase" if supabase_configured() else "mongo"


def catalog_mongo_fallback_allowed() -> bool:
    value = (os.environ.get("CATALOG_ALLOW_MONGO_FALLBACK") or "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


async def search_catalog_products(
    db: Any,
    query: str = "",
    group: str = "",
    manufacturer: str = "",
    culture: str = "",
    harmful_object: str = "",
    only_active: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    mode = catalog_backend_mode()
    if mode in {"supabase", "auto"}:
        if not supabase_configured():
            if mode == "supabase":
                raise HTTPException(status_code=503, detail="Каталог Supabase не настроен")
        else:
            try:
                return await search_supabase_products(
                    query=query,
                    group=group,
                    manufacturer=manufacturer,
                    culture=culture,
                    harmful_object=harmful_object,
                    only_active=only_active,
                    limit=limit,
                )
            except Exception as error:
                if mode == "supabase" and not catalog_mongo_fallback_allowed():
                    logger.error("Supabase catalog search failed without fallback: %s", type(error).__name__)
                    raise HTTPException(status_code=503, detail="Каталог временно недоступен")
                logger.warning("Supabase catalog search failed, using MongoDB fallback: %s", type(error).__name__)

    return await search_mongo_products(
        db,
        query=query,
        group=group,
        manufacturer=manufacturer,
        culture=culture,
        harmful_object=harmful_object,
        only_active=only_active,
        limit=limit,
    )
''',
    "strict catalog backend mode",
)
CATALOG.write_text(catalog, encoding="utf-8")
