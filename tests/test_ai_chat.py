import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.server import (
    AI_SYSTEM_PROMPT,
    AI_WEB_ALLOWED_DOMAINS,
    append_ai_sources,
    build_ai_model_messages,
    extract_ai_response_sources,
    extract_ai_search_tokens,
    generate_ai_answer,
    get_ai_output_token_limit,
    get_ai_reasoning_effort,
    get_ai_scope_refusal,
    sanitize_ai_output,
    should_force_product_web_search,
    should_use_ai_web_search,
)


class FakeResponse:
    output_text = "Проверенный ответ"

    def model_dump(self):
        return {
            "output": [
                {
                    "sources": [
                        {"title": "EPPO", "url": "https://gd.eppo.int/"},
                    ]
                }
            ]
        }


class FakeResponses:
    def __init__(self):
        self.last_request = None

    async def create(self, **kwargs):
        self.last_request = kwargs
        return FakeResponse()


class FakeAsyncOpenAI:
    last_instance = None

    def __init__(self, **kwargs):
        self.options = kwargs
        self.responses = FakeResponses()
        FakeAsyncOpenAI.last_instance = self


class AIChatTest(unittest.TestCase):
    def test_model_messages_keep_only_recent_history(self):
        history = [
            {"role": "user" if index % 2 == 0 else "assistant", "content": f"message {index}"}
            for index in range(30)
        ]
        messages = build_ai_model_messages(history, "current", {"products": []})
        self.assertEqual(len(messages), 11)
        self.assertEqual(messages[-1], {"role": "user", "content": "current"})
        self.assertEqual(messages[2]["content"], "message 22")

    def test_general_search_ignores_common_words(self):
        self.assertEqual(
            extract_ai_search_tokens("Расскажи, какие препараты содержат флорасулам"),
            ["содержат", "флорасулам"],
        )

    def test_missing_model_key_returns_readable_service_error(self):
        with patch.dict(os.environ, {"AI_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(generate_ai_answer([], "вопрос"))
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("ключ", raised.exception.detail.lower())

    def test_system_prompt_enforces_scope_and_evidence(self):
        self.assertIn("Не придумывай регистрацию", AI_SYSTEM_PROMPT)
        self.assertIn("официальный регламент РФ обязателен", AI_SYSTEM_PROMPT)
        self.assertIn("Я отвечаю только по защите растений и пестицидам", AI_SYSTEM_PROMPT)
        self.assertIn("фитопатология", AI_SYSTEM_PROMPT)
        self.assertIn("экотоксикология", AI_SYSTEM_PROMPT)
        self.assertIn("Международный опыт; не является рекомендацией", AI_SYSTEM_PROMPT)
        self.assertIn("700–1400 знаков", AI_SYSTEM_PROMPT)
        self.assertIn("Не используй Markdown-разметку", AI_SYSTEM_PROMPT)
        self.assertIn("О сложном говори простыми словами", AI_SYSTEM_PROMPT)
        self.assertIn("Не показывай пользователю URL", AI_SYSTEM_PROMPT)

    def test_web_search_is_only_enabled_for_explicit_research_requests(self):
        self.assertTrue(should_use_ai_web_search("Найди в сети последние исследования по флорасуламу"))
        self.assertTrue(should_use_ai_web_search("Проверь актуальный регламент"))
        self.assertFalse(should_use_ai_web_search("Как действует флорасулам?"))

    def test_clear_out_of_scope_request_is_refused_without_model(self):
        refusal = get_ai_scope_refusal("Кто победил в футбольном матче?")
        self.assertEqual(
            refusal,
            "Я отвечаю только по защите растений и пестицидам. "
            "Сформулируйте вопрос в этом контексте.",
        )
        self.assertIsNone(
            get_ai_scope_refusal("Как погода влияет на опрыскивание пшеницы?")
        )

    def test_output_limit_expands_only_on_request(self):
        with patch.dict(os.environ, {"AI_MAX_OUTPUT_TOKENS": ""}, clear=False):
            self.assertEqual(get_ai_output_token_limit("Ответь кратко"), 1200)
            self.assertEqual(get_ai_output_token_limit("Сделай подробный анализ"), 2000)

    def test_invalid_reasoning_effort_falls_back_to_low(self):
        with patch.dict(os.environ, {"AI_REASONING_EFFORT": "invalid"}, clear=False):
            self.assertEqual(get_ai_reasoning_effort(), "low")

    def test_practical_question_uses_medium_reasoning_by_default(self):
        with patch.dict(os.environ, {"AI_REASONING_EFFORT": ""}, clear=False):
            self.assertEqual(get_ai_reasoning_effort("Что посоветуешь против ржавчины?"), "medium")
            self.assertEqual(get_ai_reasoning_effort("Состав препарата"), "low")

    def test_product_comparison_without_verified_data_forces_web_search(self):
        self.assertTrue(should_force_product_web_search(
            "Сравни Крестраж против Колосаль Про",
            {"products": []},
        ))
        self.assertFalse(should_force_product_web_search(
            "Сравни два найденных гербицида",
            {"products": [{"product_name": "Балерина"}]},
        ))

    def test_markdown_and_links_are_removed_from_ai_output(self):
        self.assertEqual(
            sanitize_ai_output(
                "**Крестраж**\n- первый пункт\n### Вывод\n"
                "Подробнее: https://example.com/test\n\nИсточники:\n- EPPO: https://gd.eppo.int/"
            ),
            "Крестраж\n• первый пункт\nВывод\nПодробнее:",
        )

    def test_web_sources_are_extracted_and_deduplicated(self):
        response = {
            "output": [
                {"sources": [
                    {"title": "EPPO", "url": "https://gd.eppo.int/taxon/FUSACU"},
                    {"title": "EPPO duplicate", "url": "https://gd.eppo.int/taxon/FUSACU"},
                    {"title": "FRAC", "url": "https://www.frac.info/"},
                ]}
            ]
        }
        self.assertEqual(
            extract_ai_response_sources(response),
            [
                {"title": "EPPO", "url": "https://gd.eppo.int/taxon/FUSACU"},
                {"title": "FRAC", "url": "https://www.frac.info/"},
            ],
        )

    def test_responses_api_and_current_default_model_are_used(self):
        source = open("backend/server.py", encoding="utf-8").read()
        self.assertIn("ai_client.responses.create", source)
        self.assertIn('(os.environ.get("AI_MODEL") or "gpt-5.6").strip()', source)
        self.assertIn('"allowed_domains": AI_WEB_ALLOWED_DOMAINS', source)
        self.assertIn('"tool_choice": "required"', source)
        self.assertIn("force_web_search=use_web_search", source)

    def test_web_request_uses_domain_filter_but_hides_visible_sources(self):
        function_globals = generate_ai_answer.__globals__
        previous_client = function_globals.get("AsyncOpenAI")
        function_globals["AsyncOpenAI"] = FakeAsyncOpenAI
        try:
            with patch.dict(
                os.environ,
                {
                    "AI_API_KEY": "test-key",
                    "OPENAI_API_KEY": "",
                    "AI_MODEL": "",
                    "AI_MAX_OUTPUT_TOKENS": "",
                },
                clear=False,
            ):
                answer = asyncio.run(generate_ai_answer(
                    [{"role": "user", "content": "Найди в сети данные EPPO"}],
                    "Найди в сети данные EPPO",
                ))
        finally:
            if previous_client is None:
                function_globals.pop("AsyncOpenAI", None)
            else:
                function_globals["AsyncOpenAI"] = previous_client

        request = FakeAsyncOpenAI.last_instance.responses.last_request
        self.assertEqual(request["model"], "gpt-5.6")
        self.assertEqual(request["tool_choice"], "required")
        self.assertIn("eppo.int", request["tools"][0]["filters"]["allowed_domains"])
        self.assertEqual(answer, "Проверенный ответ")
        self.assertNotIn("https://", answer)

    def test_forced_product_verification_enables_web_tool(self):
        function_globals = generate_ai_answer.__globals__
        previous_client = function_globals.get("AsyncOpenAI")
        function_globals["AsyncOpenAI"] = FakeAsyncOpenAI
        try:
            with patch.dict(
                os.environ,
                {
                    "AI_API_KEY": "test-key",
                    "OPENAI_API_KEY": "",
                    "AI_MODEL": "",
                    "AI_MAX_OUTPUT_TOKENS": "",
                },
                clear=False,
            ):
                asyncio.run(generate_ai_answer(
                    [{"role": "user", "content": "Сравни Крестраж и Колосаль Про"}],
                    "Сравни Крестраж и Колосаль Про",
                    force_web_search=True,
                ))
        finally:
            if previous_client is None:
                function_globals.pop("AsyncOpenAI", None)
            else:
                function_globals["AsyncOpenAI"] = previous_client

        request = FakeAsyncOpenAI.last_instance.responses.last_request
        self.assertEqual(request["tool_choice"], "required")


if __name__ == "__main__":
    unittest.main()
