from pathlib import Path


path = Path("tests/test_ai_chat.py")
text = path.read_text(encoding="utf-8")

replacements = (
    (
        '        self.assertIn("350–800 знаков", AI_SYSTEM_PROMPT)\n',
        '        self.assertIn("700–1400 знаков", AI_SYSTEM_PROMPT)\n'
        '        self.assertIn("О сложном говори простыми словами", AI_SYSTEM_PROMPT)\n'
        '        self.assertIn("Не показывай пользователю URL", AI_SYSTEM_PROMPT)\n',
    ),
    (
        '            self.assertEqual(get_ai_output_token_limit("Ответь кратко"), 800)\n'
        '            self.assertEqual(get_ai_output_token_limit("Сделай подробный анализ"), 1600)\n',
        '            self.assertEqual(get_ai_output_token_limit("Ответь кратко"), 1200)\n'
        '            self.assertEqual(get_ai_output_token_limit("Сделай подробный анализ"), 2000)\n',
    ),
    (
        '        self.assertIn("https://gd.eppo.int/", answer)\n',
        '        self.assertEqual(answer, "Проверенный ответ")\n'
        '        self.assertNotIn("https://", answer)\n',
    ),
)

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one test fragment, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
