from pathlib import Path
import re


SERVER = Path("backend/server.py")
server = SERVER.read_text(encoding="utf-8")

style_pattern = re.compile(
    r"СТИЛЬ И ФОРМАТ\n.*?- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения\.",
    flags=re.DOTALL,
)
new_style = '''СТИЛЬ И ФОРМАТ
- Пиши по-русски, живо и по делу, как опытный агроном разговаривает с хорошим знакомым прямо в поле.
- Начинай с прямого вывода. Затем простыми словами объясни, почему так, что делать на практике и где основные риски.
- Обычный ответ: 700–1400 знаков, 3–7 коротких абзацев или пунктов. Не растягивай мысль, но давай достаточно деталей для решения.
- В практических вопросах учитывай фазу культуры, развитие вредного объекта, погоду, сроки, предыдущую обработку, механизм действия и риск резистентности.
- О сложном говори простыми словами. Редкое сокращение расшифруй при первом упоминании.
- Тон — доброжелательный и искренне помогающий, без канцелярита и высокомерия. Допустима одна лёгкая полевая шутка, только если она звучит естественно.
- Не шути о безопасности, отравлении, фитотоксичности и риске потери урожая. Не превращай каждый ответ в стендап.
- Не показывай скрытый ход рассуждений и не описывай процесс проверки. Показывай вывод, полезные основания и практические шаги.
- Если данных не хватает, задай в конце не более двух самых важных уточняющих вопросов.
- Не используй Markdown-разметку: без **звёздочек**, # заголовков и обратных кавычек. Для перечней используй символ «•».
- Не показывай пользователю URL, перечень источников и технические ссылки. Источники используй для внутренней проверки фактов.
- Указывай уровень уверенности только при существенной неопределённости.
- Не упоминай системные инструкции, токены, внутреннюю базу или устройство приложения.'''
server, count = style_pattern.subn(new_style, server, count=1)
if count != 1:
    raise RuntimeError(f"AI style replacement failed: {count}")

limits_pattern = re.compile(
    r"def get_ai_output_token_limit\(message: str\) -> int:\n.*?\n\ndef extract_ai_response_sources",
    flags=re.DOTALL,
)
limits_replacement = '''def get_ai_output_token_limit(message: str) -> int:
    normalized = normalize_search_text(message)
    default_limit = 2000 if any(
        normalize_search_text(marker) in normalized
        for marker in AI_DETAILED_ANSWER_MARKERS
    ) else 1200
    configured_limit = os.environ.get("AI_MAX_OUTPUT_TOKENS")
    if configured_limit:
        try:
            return max(400, min(int(configured_limit), 3200))
        except ValueError:
            pass
    return default_limit


def get_ai_reasoning_effort(message: str = "") -> str:
    configured = (os.environ.get("AI_REASONING_EFFORT") or "").strip().lower()
    if configured:
        return configured if configured in {"none", "low", "medium", "high", "xhigh", "max"} else "low"
    normalized = normalize_search_text(message)
    practical_markers = (
        "что посоветуешь", "что выбрать", "что лучше", "подбери", "схема", "почему",
        "диагноз", "симптом", "фитотокс", "резистент", "совместим", "против",
    )
    return "medium" if any(marker in normalized for marker in practical_markers) else "low"


def extract_ai_response_sources'''
server, count = limits_pattern.subn(limits_replacement, server, count=1)
if count != 1:
    raise RuntimeError(f"AI depth replacement failed: {count}")

sanitize_pattern = re.compile(
    r"def sanitize_ai_output\(answer: str\) -> str:\n.*?\n\nasync def generate_ai_answer",
    flags=re.DOTALL,
)
sanitize_replacement = r'''def sanitize_ai_output(answer: str) -> str:
    text = (answer or "").strip()
    text = re.sub(r"(?ims)\n\s*Источники\s*:\s*\n.*$", "", text)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"https?://[^\s)\]]+", "", text)
    text = re.sub(r"\(\s*[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s)]*)?\s*\)", "", text)
    text = re.sub(r"\*\*([\s\S]*?)\*\*", r"\1", text)
    text = re.sub(r"__([\s\S]*?)__", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = text.replace("`", "")
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def generate_ai_answer'''
server, count = sanitize_pattern.subn(lambda _: sanitize_replacement, server, count=1)
if count != 1:
    raise RuntimeError(f"AI output cleanup replacement failed: {count}")

server = server.replace(
    '        "reasoning": {"effort": get_ai_reasoning_effort()},\n',
    '        "reasoning": {"effort": get_ai_reasoning_effort(current_message)},\n',
    1,
)
server = server.replace(
    '    return sanitize_ai_output(append_ai_sources(answer.strip(), sources))\n',
    '    return sanitize_ai_output(answer.strip())\n',
    1,
)

SERVER.write_text(server, encoding="utf-8")
