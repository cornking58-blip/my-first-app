from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


server_path = Path("backend/server.py")
server = server_path.read_text()

server = replace_once(
    server,
    """3. Не придумывай регистрацию, норму, культуру, объект, действующее вещество,
   концентрацию, группу механизма действия, цену, совместимость или эффективность.
4. Для практической рекомендации в России официальный регламент РФ обязателен.""",
    """3. Не придумывай регистрацию, норму, культуру, объект, действующее вещество,
   концентрацию, группу механизма действия, цену, совместимость или эффективность.
   Любой факт о конкретном торговом препарате сообщай только тогда, когда он есть
   в переданных данных bAIkov или подтверждён источниками текущего интернет-поиска.
   Если подтверждения нет, прямо скажи, что данные не подтверждены, и не угадывай.
4. Для практической рекомендации в России официальный регламент РФ обязателен.""",
    "prompt evidence guard",
)

server = replace_once(
    server,
    """СТИЛЬ И ФОРМАТ
- Пиши по-русски, партнёрски и спокойно, языком практикующего агронома.
- Начинай с вывода. Без приветствий, воды, саморекламы и повторения вопроса.
- Обычный ответ: ориентир 600–1200 знаков, до 3–6 коротких пунктов.
- Если пользователь просит подробно, допускается развёрнутый ответ, но без повторов.
- Расшифровывай редкое сокращение при первом упоминании.
- Указывай уровень уверенности, только когда есть существенная неопределённость.
- При интернет-поиске подкрепляй существенные утверждения ссылками и используй
  только разрешённые авторитетные источники. Если подтверждения нет, так и скажи.
- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения.""",
    """СТИЛЬ И ФОРМАТ
- Пиши по-русски, живо и по делу, как практикующий агроном разговаривает с коллегой.
- Начинай с прямого ответа. Без приветствий, воды, саморекламы и повторения вопроса.
- Обычный ответ: 350–800 знаков, 2–5 коротких абзацев или пунктов.
- Не показывай ход рассуждений и не описывай процесс проверки. Пользователь должен
  видеть вывод и только те основания, которые реально помогают принять решение.
- Не перечисляй препарат, который нельзя рекомендовать, если пользователь не спросил
  о нём напрямую. При прямом вопросе достаточно одной короткой фразы об ограничении.
- Не используй Markdown-разметку: без **звёздочек**, # заголовков и обратных кавычек.
  Для перечней используй обычный символ «•», названия препаратов пиши без выделения.
- Если пользователь просит подробно, допускается развёрнутый ответ, но без повторов.
- Расшифровывай редкое сокращение при первом упоминании.
- Указывай уровень уверенности только при существенной неопределённости.
- При интернет-поиске подкрепляй существенные утверждения ссылками и используй
  только разрешённые авторитетные источники. Если подтверждения нет, так и скажи.
- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения.""",
    "prompt style",
)

server = replace_once(
    server,
    '    "mcx.gov.ru",\n',
    '    "mcx.gov.ru",\n    "agroex.ru",\n    "avgust.com",\n',
    "manufacturer domains",
)

product_helpers = '''AI_PRODUCT_SPECIFIC_MARKERS = (
    "сравни",
    "сравнение",
    "против",
    "что лучше",
    "какой лучше",
    "чем отличается",
    "состав препарата",
    "действующие вещества препарата",
    "регистрация препарата",
    "норма препарата",
)


def is_product_specific_question(message: str) -> bool:
    normalized = normalize_search_text(message)
    return any(normalize_search_text(marker) in normalized for marker in AI_PRODUCT_SPECIFIC_MARKERS)


def context_has_verified_product_data(context: Dict[str, Any]) -> bool:
    if context.get("comparison"):
        return True
    products = context.get("products")
    return isinstance(products, list) and len(products) > 0


def should_force_product_web_search(message: str, context: Dict[str, Any]) -> bool:
    return is_product_specific_question(message) and not context_has_verified_product_data(context)


'''
server = replace_once(
    server,
    "AI_PLANT_PROTECTION_MARKERS = (\n",
    product_helpers + "AI_PLANT_PROTECTION_MARKERS = (\n",
    "product verification helpers",
)

server = replace_once(
    server,
    """    default_limit = 2400 if any(
        normalize_search_text(marker) in normalized
        for marker in AI_DETAILED_ANSWER_MARKERS
    ) else 1200""",
    """    default_limit = 1600 if any(
        normalize_search_text(marker) in normalized
        for marker in AI_DETAILED_ANSWER_MARKERS
    ) else 800""",
    "output token defaults",
)
server = replace_once(
    server,
    "            return max(400, min(int(configured_limit), 4000))",
    "            return max(300, min(int(configured_limit), 2400))",
    "output token clamp",
)
server = replace_once(
    server,
    '    value = (os.environ.get("AI_REASONING_EFFORT") or "medium").strip().lower()',
    '    value = (os.environ.get("AI_REASONING_EFFORT") or "low").strip().lower()',
    "reasoning default",
)
server = replace_once(
    server,
    '    return value if value in {"none", "low", "medium", "high", "xhigh", "max"} else "medium"',
    '    return value if value in {"none", "low", "medium", "high", "xhigh", "max"} else "low"',
    "reasoning fallback",
)
server = replace_once(server, "    if len(context_json) > 30000:", "    if len(context_json) > 16000:", "context condition")
server = replace_once(server, '        context_json = context_json[:30000] + "\\n[контекст сокращён]"', '        context_json = context_json[:16000] + "\\n[контекст сокращён]"', "context truncation")
server = replace_once(server, "    for item in list(history)[-16:]:", "    for item in list(history)[-8:]:", "history limit")

sanitize_helper = '''def sanitize_ai_output(answer: str) -> str:
    text = (answer or "").strip()
    text = re.sub(r"\\*\\*([\\s\\S]*?)\\*\\*", r"\\1", text)
    text = re.sub(r"__([\\s\\S]*?)__", r"\\1", text)
    text = re.sub(r"(?m)^\\s*#{1,6}\\s*", "", text)
    text = text.replace("`", "")
    text = re.sub(r"(?m)^\\s*[-*]\\s+", "• ", text)
    text = re.sub(r"\\n{3,}", "\\n\\n", text)
    return text.strip()


'''
server = replace_once(server, "async def generate_ai_answer(\n", sanitize_helper + "async def generate_ai_answer(\n", "output sanitizer")
server = replace_once(server, "    return append_ai_sources(answer.strip(), sources)", "    return sanitize_ai_output(append_ai_sources(answer.strip(), sources))", "sanitize answer")

server = replace_once(
    server,
    """            use_web_search = should_use_ai_web_search(content)
            reservation = await reserve_ai_usage(current_user, use_web_search)
            context = await build_ai_chat_context(chat, content)
            model_messages = build_ai_model_messages(chat.get("messages", []), content, context)""",
    """            context = await build_ai_chat_context(chat, content)
            use_web_search = (
                should_use_ai_web_search(content)
                or should_force_product_web_search(content, context)
            )
            reservation = await reserve_ai_usage(current_user, use_web_search)
            model_messages = build_ai_model_messages(chat.get("messages", []), content, context)""",
    "automatic product verification",
)

server_path.write_text(server)

ai_path = Path("frontend/app/ai.tsx")
ai = ai_path.read_text()
formatter = '''
const formatMessageText = (value: string) => value
  .replace(/\\*\\*([\\s\\S]*?)\\*\\*/g, '$1')
  .replace(/__([\\s\\S]*?)__/g, '$1')
  .replace(/^\\s*#{1,6}\\s*/gm, '')
  .replace(/`/g, '')
  .replace(/^\\s*[-*]\\s+/gm, '• ')
  .replace(/\\n{3,}/g, '\\n\\n')
  .trim();
'''
ai = replace_once(
    ai,
    """const getOptionalNumber = (value?: string) => {
  if (!value) return undefined;
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : undefined;
};
""",
    """const getOptionalNumber = (value?: string) => {
  if (!value) return undefined;
  const parsed = Number(value.replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : undefined;
};
""" + formatter,
    "frontend formatter",
)
ai = replace_once(ai, "<Text style={styles.messageText}>{message.content}</Text>", "<Text style={styles.messageText}>{formatMessageText(message.content)}</Text>", "frontend output")
ai_path.write_text(ai)


test_path = Path("tests/test_ai_chat.py")
tests = test_path.read_text()
tests = replace_once(
    tests,
    'sanitize_ai_chat_context = namespace["sanitize_ai_chat_context"]\nshould_use_ai_web_search = namespace["should_use_ai_web_search"]',
    'sanitize_ai_chat_context = namespace["sanitize_ai_chat_context"]\nsanitize_ai_output = namespace["sanitize_ai_output"]\nshould_force_product_web_search = namespace["should_force_product_web_search"]\nshould_use_ai_web_search = namespace["should_use_ai_web_search"]',
    "test exports",
)
tests = replace_once(tests, "        self.assertEqual(len(messages), 19)", "        self.assertEqual(len(messages), 11)", "history length")
tests = replace_once(tests, '        self.assertEqual(messages[2]["content"], "message 14")', '        self.assertEqual(messages[2]["content"], "message 22")', "history first")
tests = replace_once(tests, '        self.assertIn("600–1200 знаков", AI_SYSTEM_PROMPT)', '        self.assertIn("350–800 знаков", AI_SYSTEM_PROMPT)\n        self.assertIn("Не используй Markdown-разметку", AI_SYSTEM_PROMPT)', "prompt test")
tests = replace_once(tests, '            self.assertEqual(get_ai_output_token_limit("Ответь кратко"), 1200)\n            self.assertEqual(get_ai_output_token_limit("Сделай подробный анализ"), 2400)', '            self.assertEqual(get_ai_output_token_limit("Ответь кратко"), 800)\n            self.assertEqual(get_ai_output_token_limit("Сделай подробный анализ"), 1600)', "output tests")
tests = replace_once(tests, '    def test_invalid_reasoning_effort_falls_back_to_medium(self):\n        with patch.dict(os.environ, {"AI_REASONING_EFFORT": "invalid"}, clear=False):\n            self.assertEqual(get_ai_reasoning_effort(), "medium")', '    def test_invalid_reasoning_effort_falls_back_to_low(self):\n        with patch.dict(os.environ, {"AI_REASONING_EFFORT": "invalid"}, clear=False):\n            self.assertEqual(get_ai_reasoning_effort(), "low")', "reasoning test")

new_tests = '''
    def test_product_comparison_without_verified_data_forces_web_search(self):
        self.assertTrue(should_force_product_web_search(
            "Сравни Крестраж против Колосаль Про",
            {"products": []},
        ))
        self.assertFalse(should_force_product_web_search(
            "Сравни два найденных гербицида",
            {"products": [{"product_name": "Балерина"}]},
        ))

    def test_markdown_is_removed_from_ai_output(self):
        self.assertEqual(
            sanitize_ai_output("**Крестраж**\\n- первый пункт\\n### Вывод"),
            "Крестраж\\n• первый пункт\\nВывод",
        )
'''
tests = replace_once(tests, "    def test_web_sources_are_extracted_and_deduplicated(self):\n", new_tests + "\n    def test_web_sources_are_extracted_and_deduplicated(self):\n", "new tests")
tests = replace_once(tests, '        self.assertIn("baikov_ai_client_id", CLIENT_ID_SOURCE)\n', '        self.assertIn("baikov_ai_client_id", CLIENT_ID_SOURCE)\n        self.assertIn("formatMessageText(message.content)", AI_SCREEN_SOURCE)\n', "frontend test")
test_path.write_text(tests)
