from pathlib import Path

path = Path("backend/strict_catalog_ai.py")
text = path.read_text(encoding="utf-8")
old = '''async def find_catalog_product(db: Any, product_name: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:\n    results = await search_catalog_candidate_products(db, product_name, limit=12)\n'''
new = '''async def find_catalog_product(db: Any, product_name: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:\n    mode = catalog_backend_mode()\n    results = await search_catalog_candidate_products(db, product_name, limit=12)\n'''
if text.count(old) != 1:
    raise RuntimeError(f"expected one target, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
