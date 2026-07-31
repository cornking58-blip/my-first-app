from pathlib import Path

path = Path("backend/strict_catalog_ai.py")
text = path.read_text(encoding="utf-8")
old = r"протравител(?:е|я|ем)?"
new = r"протравител(?:ь|е|я|ем)?"
if text.count(old) != 1:
    raise RuntimeError(f"expected one seed-treatment prefix pattern, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
Path("scripts/fix_seed_treatment_prefix.py").unlink(missing_ok=True)
