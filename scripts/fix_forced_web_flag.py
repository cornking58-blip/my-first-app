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
    '''async def generate_ai_answer(
    messages: List[Dict[str, str]],
    current_message: str = "",
) -> str:''',
    '''async def generate_ai_answer(
    messages: List[Dict[str, str]],
    current_message: str = "",
    force_web_search: bool = False,
) -> str:''',
    "generate signature",
)
server = replace_once(
    server,
    "    use_web_search = should_use_ai_web_search(current_message)",
    "    use_web_search = should_use_ai_web_search(current_message) or force_web_search",
    "forced web flag",
)
server = replace_once(
    server,
    "            answer = await generate_ai_answer(model_messages, content)",
    "            answer = await generate_ai_answer(\n                model_messages,\n                content,\n                force_web_search=use_web_search,\n            )",
    "endpoint flag forwarding",
)
server_path.write_text(server)


test_path = Path("tests/test_ai_chat.py")
tests = test_path.read_text()
tests = replace_once(
    tests,
    '        self.assertIn(\'"tool_choice": "required"\', SERVER_SOURCE)\n',
    '        self.assertIn(\'"tool_choice": "required"\', SERVER_SOURCE)\n        self.assertIn("force_web_search=use_web_search", SERVER_SOURCE)\n',
    "static forced web test",
)

new_test = '''
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
'''

tests = replace_once(
    tests,
    "\n\nclass AIChatFrontendStaticTest(unittest.TestCase):\n",
    new_test + "\n\nclass AIChatFrontendStaticTest(unittest.TestCase):\n",
    "functional forced web test",
)
test_path.write_text(tests)
