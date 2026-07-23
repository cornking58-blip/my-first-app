from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


root = Path(__file__).resolve().parents[1]
server_path = root / "backend" / "server.py"
test_path = root / "tests" / "test_ai_chat.py"
server = server_path.read_text()
tests = test_path.read_text()

old_style = '''СТИЛЬ И ФОРМАТ
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
- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения.
'''
new_style = '''СТИЛЬ И ФОРМАТ
- Пиши по-русски, как опытный товарищ-агроном рядом в поле: спокойно, просто, прямо
  и с искренним желанием довести пользователя до рабочего решения.
- Начинай с практического вывода. Не начинай ответ словами «корректно сравнить нельзя»,
  если можно дать полезный вывод по регистрации, составу, механизму или технологии.
- Обычный ответ: 450–1000 знаков, 2–6 коротких абзацев или пунктов.
- Не показывай ход рассуждений и не описывай процесс проверки. Пользователь должен
  видеть решение и только те основания, которые реально помогают принять решение.
- Если выбранные препараты не зарегистрированы против указанного объекта, не заканчивай
  сухим отказом: коротко скажи «из этих двух — ни один по регламенту» и предложи, что
  проверить или применить вместо них на уровне технологии или действующих веществ.
- Не проси фото этикетки, когда данные можно найти на официальном сайте производителя,
  в каталоге или регистрационном источнике. Уточняющий вопрос задавай только после
  лучшего доступного ответа и не более одного за раз.
- В запросах «все препараты», «выпиши каталог», «все протравители от компании» сначала
  распознай компанию как производителя, открой её официальный каталог и постарайся дать
  полный перечень нужной категории, а не два-три примера.
- Допускается одна лёгкая полевая шутка или живая фраза, если она уместна. Не шути про
  безопасность, отравления, фитотоксичность, потерю урожая и юридические ограничения.
- Не используй Markdown-разметку: без **звёздочек**, # заголовков и обратных кавычек.
  Для перечней используй обычный символ «•», названия препаратов пиши без выделения.
- Если пользователь просит подробно, допускается развёрнутый ответ, но без повторов.
- Расшифровывай редкое сокращение при первом упоминании.
- Указывай уровень уверенности только при существенной неопределённости.
- При интернет-поиске подкрепляй существенные утверждения ссылками и используй
  официальные сайты, регуляторов и авторитетные источники. Если факт не подтверждён,
  отдели его от подтверждённых данных, но всё равно дай максимально полезный вывод.
- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения.
'''
server = replace_once(server, old_style, new_style, "style prompt")

old_intents = '''AI_PRODUCT_SPECIFIC_MARKERS = (
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
new_intents = '''AI_PRODUCT_SPECIFIC_MARKERS = (
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

AI_CATALOG_LIST_MARKERS = (
    "все препараты",
    "все протравители",
    "все фунгициды",
    "все гербициды",
    "все инсектициды",
    "полный список",
    "выпиши все",
    "перечисли все",
    "каталог",
    "линейка препаратов",
    "ассортимент",
)

AI_PRODUCT_CATEGORY_MARKERS = (
    "протравител",
    "обработка семян",
    "гербицид",
    "фунгицид",
    "инсектицид",
    "акарицид",
    "десикант",
    "адъювант",
    "регулятор роста",
)

AI_COMPANY_MARKERS = (
    "производител",
    "компани",
    "бренд",
    "фирм",
    " от ",
)

AI_KNOWN_COMPANY_DOMAINS = {
    "agroexpert group": "agroex.ru",
    "agro expert group": "agroex.ru",
    "агроэкспертгрупп": "agroex.ru",
    "агро эксперт групп": "agroex.ru",
    "агроэксперт групп": "agroex.ru",
}


def is_product_specific_question(message: str) -> bool:
    normalized = normalize_search_text(message)
    return any(normalize_search_text(marker) in normalized for marker in AI_PRODUCT_SPECIFIC_MARKERS)


def is_company_catalog_question(message: str) -> bool:
    normalized = normalize_search_text(message)
    has_list_intent = any(normalize_search_text(marker) in normalized for marker in AI_CATALOG_LIST_MARKERS)
    has_category = any(normalize_search_text(marker) in normalized for marker in AI_PRODUCT_CATEGORY_MARKERS)
    has_company = any(normalize_search_text(marker) in normalized for marker in AI_COMPANY_MARKERS)
    has_known_company = any(alias in normalized for alias in AI_KNOWN_COMPANY_DOMAINS)
    return has_list_intent and has_category and (has_company or has_known_company)


def get_known_company_domain(message: str) -> Optional[str]:
    normalized = normalize_search_text(message)
    for alias, domain in AI_KNOWN_COMPANY_DOMAINS.items():
        if alias in normalized:
            return domain
    return None


def context_has_verified_product_data(context: Dict[str, Any]) -> bool:
    if context.get("comparison"):
        return True
    products = context.get("products")
    return isinstance(products, list) and len(products) > 0


def should_force_product_web_search(message: str, context: Dict[str, Any]) -> bool:
    return is_product_specific_question(message) and not context_has_verified_product_data(context)


def should_force_company_web_search(message: str, context: Dict[str, Any]) -> bool:
    return is_company_catalog_question(message)
'''
server = replace_once(server, old_intents, new_intents, "intent helpers")

old_history = '''    for item in list(history)[-8:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": current_message})
    return messages


def sanitize_ai_output(answer: str) -> str:
'''
new_history = '''    history_items = list(history)
    older_items = history_items[:-12]
    if older_items:
        older_digest = []
        for item in older_items[-8:]:
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                label = "Пользователь" if role == "user" else "bAIkov AI"
                older_digest.append(f"{label}: {content[:220]}")
        if older_digest:
            messages.append({
                "role": "system",
                "content": "Краткий контекст более ранней части диалога:\n" + "\n".join(older_digest),
            })

    for item in history_items[-12:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": current_message})
    return messages


def build_ai_research_brief(message: str, context: Dict[str, Any]) -> str:
    lines = [
        "Проведи предметный поиск перед ответом. Не ищи вопрос одной длинной фразой.",
        "Сначала выдели торговые названия препаратов, компанию-производителя, категорию, культуру и вредный объект.",
        "Каждое торговое название и каждую компанию ищи отдельным точным запросом.",
        "Приоритет: официальный сайт производителя, официальный каталог, регистрационные данные РФ, затем авторитетные справочники.",
    ]
    known_domain = get_known_company_domain(message)
    if known_domain:
        lines.append(f"Для названной компании в первую очередь проверь официальный домен {known_domain} и его каталог продукции.")
    if is_company_catalog_question(message):
        lines.extend([
            "Это запрос на каталог производителя. Найди страницу нужной категории и перечисли максимально полный набор продуктов.",
            "Не заменяй полный перечень несколькими примерами. Если полнота не гарантирована, честно укажи это одной короткой фразой.",
        ])
    if is_product_specific_question(message):
        lines.extend([
            "Для каждого препарата отдельно подтверди состав, концентрации, препаративную форму и действующую регистрацию.",
            "Отдельно проверь культуру и целевой объект. Если объект не указан в регламенте, дай полезный вывод: кто подходит по регламенту или что искать вместо них.",
            "Не проси фото этикетки, пока не исчерпаны официальные открытые источники.",
        ])
    lines.append("После проверки ответь по существу, человеческим языком, без описания самого процесса поиска.")
    return "\n".join(lines)


def sanitize_ai_output(answer: str) -> str:
'''
server = replace_once(server, old_history, new_history, "history and research brief")

old_generate_setup = '''    ai_client = AsyncOpenAI(**client_options)
    use_web_search = should_use_ai_web_search(current_message) or force_web_search
    request_options: Dict[str, Any] = {
        "model": (os.environ.get("AI_MODEL") or "gpt-5.6").strip(),
        "input": messages,
        "reasoning": {"effort": get_ai_reasoning_effort()},
        "max_output_tokens": get_ai_output_token_limit(current_message),
        "extra_body": {
            "prompt_cache_key": "baikov:plant-protection-assistant:v1",
        },
    }
'''
new_generate_setup = '''    ai_client = AsyncOpenAI(**client_options)
    use_web_search = should_use_ai_web_search(current_message) or force_web_search
    request_messages = list(messages)
    if use_web_search:
        request_messages.append({
            "role": "system",
            "content": build_ai_research_brief(current_message, {}),
        })
    request_options: Dict[str, Any] = {
        "model": (os.environ.get("AI_MODEL") or "gpt-5.6").strip(),
        "input": request_messages,
        "reasoning": {"effort": "medium" if use_web_search else get_ai_reasoning_effort()},
        "max_output_tokens": max(1000, get_ai_output_token_limit(current_message)) if use_web_search else get_ai_output_token_limit(current_message),
        "extra_body": {
            "prompt_cache_key": "baikov:plant-protection-assistant:v2",
        },
    }
'''
server = replace_once(server, old_generate_setup, new_generate_setup, "generate setup")

old_source_fallback = '''    answer = getattr(response, "output_text", None)
    if not answer or not answer.strip():
        raise HTTPException(status_code=502, detail="ИИ вернул пустой ответ. Попробуйте ещё раз.")
    sources = extract_ai_response_sources(response) if use_web_search else []
    if use_web_search and not sources:
        return (
            "Не удалось подтвердить ответ по разрешённым авторитетным источникам. "
            "Уточните культуру, вредный объект, регион и какой именно факт нужно проверить."
        )
    return sanitize_ai_output(append_ai_sources(answer.strip(), sources))
'''
new_source_fallback = '''    answer = getattr(response, "output_text", None)
    if not answer or not answer.strip():
        raise HTTPException(status_code=502, detail="ИИ вернул пустой ответ. Попробуйте ещё раз.")
    sources = extract_ai_response_sources(response) if use_web_search else []

    if use_web_search and not sources:
        fallback_options = dict(request_options)
        fallback_options["input"] = request_messages + [{
            "role": "system",
            "content": (
                "Первый поиск не дал пригодных ссылок. Повтори поиск шире: сначала найди официальный сайт производителя "
                "или официальный каталог, затем регистрационные данные и авторитетные отраслевые источники. "
                "Не выдумывай факты, но обязательно постарайся дать практический ответ."
            ),
        }]
        fallback_options["tools"] = [{"type": "web_search"}]
        try:
            response = await ai_client.responses.create(**fallback_options)
            answer = getattr(response, "output_text", None)
            sources = extract_ai_response_sources(response)
        except Exception as error:
            logger.warning("AI fallback web search failed: %s", type(error).__name__)

    if not answer or not answer.strip():
        raise HTTPException(status_code=502, detail="ИИ вернул пустой ответ. Попробуйте ещё раз.")
    if use_web_search and not sources:
        return (
            "Не нашёл достаточно надёжных открытых данных, чтобы назвать состав или регламент без риска ошибки. "
            "Напишите точное торговое название и производителя — попробую ещё раз по официальному каталогу."
        )
    return sanitize_ai_output(append_ai_sources(answer.strip(), sources))
'''
server = replace_once(server, old_source_fallback, new_source_fallback, "web fallback")

old_endpoint = '''            use_web_search = (
                should_use_ai_web_search(content)
                or should_force_product_web_search(content, context)
            )
'''
new_endpoint = '''            use_web_search = (
                should_use_ai_web_search(content)
                or should_force_product_web_search(content, context)
                or should_force_company_web_search(content, context)
            )
'''
server = replace_once(server, old_endpoint, new_endpoint, "endpoint web intent")

old_namespace = '''should_force_product_web_search = namespace["should_force_product_web_search"]
should_use_ai_web_search = namespace["should_use_ai_web_search"]
'''
new_namespace = '''build_ai_research_brief = namespace["build_ai_research_brief"]
is_company_catalog_question = namespace["is_company_catalog_question"]
should_force_company_web_search = namespace["should_force_company_web_search"]
should_force_product_web_search = namespace["should_force_product_web_search"]
should_use_ai_web_search = namespace["should_use_ai_web_search"]
'''
tests = replace_once(tests, old_namespace, new_namespace, "test namespace")

old_history_test = '''        messages = build_ai_model_messages(history, "current", {"products": []})
        self.assertEqual(len(messages), 11)
        self.assertEqual(messages[-1], {"role": "user", "content": "current"})
        self.assertEqual(messages[2]["content"], "message 22")
'''
new_history_test = '''        messages = build_ai_model_messages(history, "current", {"products": []})
        self.assertEqual(len(messages), 16)
        self.assertEqual(messages[-1], {"role": "user", "content": "current"})
        self.assertIn("Краткий контекст", messages[2]["content"])
        self.assertEqual(messages[3]["content"], "message 18")
'''
tests = replace_once(tests, old_history_test, new_history_test, "history test")

old_prompt_asserts = '''        self.assertIn("350–800 знаков", AI_SYSTEM_PROMPT)
        self.assertIn("Не используй Markdown-разметку", AI_SYSTEM_PROMPT)
'''
new_prompt_asserts = '''        self.assertIn("450–1000 знаков", AI_SYSTEM_PROMPT)
        self.assertIn("товарищ-агроном", AI_SYSTEM_PROMPT)
        self.assertIn("одна лёгкая полевая шутка", AI_SYSTEM_PROMPT)
        self.assertIn("Не используй Markdown-разметку", AI_SYSTEM_PROMPT)
'''
tests = replace_once(tests, old_prompt_asserts, new_prompt_asserts, "prompt tests")

insert_after_product_test = '''        self.assertFalse(should_force_product_web_search(
            "Сравни два найденных гербицида",
            {"products": [{"product_name": "Балерина"}]},
        ))

'''
company_tests = '''        self.assertFalse(should_force_product_web_search(
            "Сравни два найденных гербицида",
            {"products": [{"product_name": "Балерина"}]},
        ))

    def test_company_catalog_request_forces_official_web_search(self):
        message = "Выпиши все протравители от Agroexpert Group"
        self.assertTrue(is_company_catalog_question(message))
        self.assertTrue(should_force_company_web_search(message, {"products": []}))
        brief = build_ai_research_brief(message, {})
        self.assertIn("agroex.ru", brief)
        self.assertIn("максимально полный набор", brief)

'''
tests = replace_once(tests, insert_after_product_test, company_tests, "company tests")

old_static_asserts = '''        self.assertIn('"tool_choice": "required"', SERVER_SOURCE)
        self.assertIn("force_web_search=use_web_search", SERVER_SOURCE)
'''
new_static_asserts = '''        self.assertIn('"tool_choice": "required"', SERVER_SOURCE)
        self.assertIn("force_web_search=use_web_search", SERVER_SOURCE)
        self.assertIn("fallback_options", SERVER_SOURCE)
        self.assertIn("should_force_company_web_search", SERVER_SOURCE)
        self.assertIn('"medium" if use_web_search', SERVER_SOURCE)
'''
tests = replace_once(tests, old_static_asserts, new_static_asserts, "static assertions")

server_path.write_text(server)
test_path.write_text(tests)
print("Field advisor AI patch applied")
