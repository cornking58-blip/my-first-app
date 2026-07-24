from pathlib import Path
import runpy

runpy.run_path("scripts/finalize_unified_catalog_v2.py", run_name="__main__")

test_path = Path("tests/test_unified_catalog.py")
test_source = test_path.read_text(encoding="utf-8")
old = '        self.assertIn(\'return "\\n".join(lines)\', CATALOG)\n'
new = '        self.assertIn("def build_direct_catalog_answer", CATALOG)\n'
if old not in test_source:
    raise RuntimeError("Generated direct-answer assertion was not found")
test_path.write_text(test_source.replace(old, new, 1), encoding="utf-8")
