from pathlib import Path

path = Path("frontend/app/account.tsx")
text = path.read_text(encoding="utf-8")

replacements = {
    "{ width: `${progress * 100}%` }": "{ width: `${progress * 100}%` as `${number}%` }",
    "fontWeight: '750'": "fontWeight: '700'",
    "fontWeight: '650'": "fontWeight: '600'",
}

for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new)
    elif new not in text:
        raise RuntimeError(f"Account type fix pattern not found: {old}")

path.write_text(text, encoding="utf-8")
