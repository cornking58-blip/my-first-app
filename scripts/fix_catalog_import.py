from pathlib import Path

path = Path("backend/server.py")
text = path.read_text(encoding="utf-8")
old = "from product_catalog import build_catalog_ai_context, build_direct_catalog_answer, create_products_router\n"
new = '''try:
    from .product_catalog import build_catalog_ai_context, build_direct_catalog_answer, create_products_router
except ImportError:
    from product_catalog import build_catalog_ai_context, build_direct_catalog_answer, create_products_router
'''
if text.count(old) != 1:
    raise RuntimeError("Catalog import line was not found exactly once")
text = text.replace(old, new, 1)
text = text.replace(
    'app = FastAPI(title="Herbicides API", version="1.0.0")',
    'app = FastAPI(title="Pesticides API", version="1.0.0")',
    1,
)
path.write_text(text, encoding="utf-8")
