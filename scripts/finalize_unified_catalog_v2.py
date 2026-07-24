from pathlib import Path
import runpy

runpy.run_path("scripts/finalize_unified_catalog.py", run_name="__main__")

catalog_path = Path("backend/product_catalog.py")
catalog = catalog_path.read_text(encoding="utf-8")
broken = '    return "\n".join(lines)'
fixed = '    return "\\n".join(lines)'
if broken not in catalog:
    raise RuntimeError("Direct catalog answer line was not generated as expected")
catalog_path.write_text(catalog.replace(broken, fixed, 1), encoding="utf-8")
