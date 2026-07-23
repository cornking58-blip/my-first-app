"""Runtime enhancement for bAIkov AI research and tone.

This module is loaded automatically by Python as ``sitecustomize`` in Railway's
backend working directory. It wraps the OpenAI Responses client without changing
public backend routes.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Sequence


def _normalize(value: str) -> str:
    value = (value or "").strip().lower().replace("ё", "е")
    value = re.sub(r"[^0-9a-zа-яе]+", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


_CATALOG_MARKERS = (
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

_CATEGORY_MARKERS = (
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

_COMPANY_MARKERS = (
    "производител",
    "компани",
    "бренд",
    "фирм",
    " от ",
)

_PRODUCT_RESEARCH_MARKERS = (
    "сравни",
    "сравнение",
    "против",
    "что лучше",
    "какой лучше",
    "чем отличается",
    "состав",
    "регистрация",
    "норма",
)

_PLANT_PROTECTION_MARKERS = (
    "агроном",
    "растени",
    "культур",
    "пшениц",
    "ячмен",
    "подсолнеч",
    "кукуруз",
    "соя",
    "рапс",
    "сорня",
    "вредител",
    "болезн",
    "плесен",
    "ржавчин",
    "фузари",
    "гербиц",
    "фунгиц",
    "инсектиц",
    "протрав",
    "пестиц",
    "препарат",
)

_KNOWN_COMPANIES = {
    "agroexpert group": ("Агро Эксперт Груп", "agroex.ru", "https://agroex.ru/catalog/"),
    "agro expert group": ("Агро Эксперт Груп", "agroex.ru", "https://agroex.ru/catalog/"),
    "агроэкспертгрупп": ("Агро Эксперт Груп", "agroex.ru", "https://agroex.ru/catalog/"),
    "агро эксперт групп": ("Агро Эксперт Груп", "agroex.ru", "https://agroex.ru/catalog/"),
    "агроэксперт групп": ("Агро Эксперт Груп", "agroex.ru", "https://agroex.ru/catalog/"),
}


def _is_company_catalog_request(message: str) -> bool:
    normalized = _normalize(message)
    has_list = any(_normalize(marker) in normalized for marker in _CATALOG_MARKERS)
    has_category = any(_normalize(marker) in normalized for marker in _CATEGORY_MARKERS)
    has_company = any(_normalize(marker) in normalized for marker in _COMPANY_MARKERS)
    has_known_company = any(alias in normalized for alias in _KNOWN_COMPANIES)
    return has_list and has_category and (has_company or has_known_company)


def _is_product_research_request(message: str) -> bool:
    normalized = _normalize(message)
    return any(_normalize(marker) in normalized for marker in _PRODUCT_RESEARCH_MARKERS)


def _is_plant_protection_request(message: str) -> bool:
    normalized = _normalize(message)
    return any(marker in normalized for marker in _PLANT_PROTECTION_MARKERS)


def _known_company(message: str):
    normalized = _normalize(message)
    for alias, details in _KNOWN_COMPANIES.items():
        if alias in normalized:
            return details
    return None


def _last_user_message(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for item in reversed(messages):
        if isinstance(item, dict) and item.get("role") == "user":
            return str(item.get("content") or "").strip()
    return ""


def _field_advisor_prompt() -> str:
    return (
        "Отвечай как опытный товарищ-агроном рядом в поле: спокойно, просто, прямо и с искренним желанием помочь. "
        "Сначала дай практический вывод, затем коротко объясни основания. Не говори языком юридического отдела и не описывай ход поиска. "
        "Если выбранные препараты не зарегистрированы против указанного объекта, не ограничивайся отказом: скажи, что из этих двух по регламенту не подходит ни один, "
        "и предложи рабочее направление — технологию, группу действующих веществ или уточнение, которое действительно меняет решение. "
        "Не проси фото этикетки, пока не исчерпаны официальный сайт производителя, каталог и регистрационные данные. "
        "Допускается одна лёгкая полевая шутка, но не в вопросах безопасности, фитотоксичности и риска потери урожая. "
        "Не используй Markdown-звёздочки и технические заголовки."
    )


def _research_prompt(message: str) -> str:
    lines = [
        "Проведи предметный поиск перед ответом. Не ищи весь вопрос одной длинной фразой.",
        "Сначала выдели торговые названия препаратов, производителя, категорию продукта, культуру и вредный объект.",
        "Каждое торговое название и каждого производителя ищи отдельным точным запросом.",
        "Приоритет источников: официальный сайт производителя, официальный каталог, регистрационные данные РФ, затем авторитетные отраслевые справочники.",
    ]
    company = _known_company(message)
    if company:
        company_name, domain, catalog_url = company
        lines.append(
            f"В запросе названа компания {company_name}. Сначала открой её официальный домен {domain} и каталог {catalog_url}."
        )
    if _is_company_catalog_request(message):
        lines.extend([
            "Это запрос на полный каталог конкретной категории производителя.",
            "Найди страницу категории и перечисли все найденные продукты этой категории, а не два-три примера.",
            "Для каждого продукта по возможности укажи тип, состав и назначение кратко. Если полнота страницы сомнительна, скажи об этом одной фразой в конце.",
            "В ответе обязательно приведи прямую ссылку на официальный каталог или страницу категории.",
        ])
    if _is_product_research_request(message):
        lines.extend([
            "Для каждого препарата отдельно подтверди состав, концентрации, препаративную форму и регистрацию.",
            "Отдельно проверь культуру и указанный вредный объект. Не смешивай болезни по вегетации, протравливание семян и осенние обработки.",
            "Если объект не заявлен в регламенте, всё равно дай полезный агрономический вывод и направление, что искать вместо выбранных вариантов.",
            "В ответе обязательно приведи прямые ссылки на использованные страницы.",
        ])
    lines.append("После проверки ответь по существу человеческим языком, без рассказа о самом процессе поиска.")
    return "\n".join(lines)


def _extract_sources(response: Any, limit: int = 6) -> List[Dict[str, str]]:
    try:
        payload = response.model_dump() if hasattr(response, "model_dump") else response
    except Exception:
        return []
    sources: List[Dict[str, str]] = []
    seen = set()

    def visit(value: Any) -> None:
        if len(sources) >= limit:
            return
        if isinstance(value, dict):
            url = value.get("url")
            if isinstance(url, str) and url.startswith(("https://", "http://")) and url not in seen:
                seen.add(url)
                title = value.get("title") or value.get("name") or "Источник"
                sources.append({"title": str(title).strip()[:160], "url": url})
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(payload)
    return sources


def _append_sources(text: str, sources: Sequence[Dict[str, str]]) -> str:
    if not sources:
        return text
    existing = text or ""
    fresh = [source for source in sources if source["url"] not in existing]
    if not fresh:
        return text
    lines = [existing.rstrip(), "", "Источники:"]
    lines.extend(f"• {source['title']}: {source['url']}" for source in fresh)
    return "\n".join(lines).strip()


class _ResponseProxy:
    def __init__(self, response: Any, output_text: str):
        self._response = response
        self.output_text = output_text

    def model_dump(self, *args, **kwargs):
        return self._response.model_dump(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._response, name)


def _install_patch() -> None:
    try:
        import openai as openai_module
    except Exception:
        return

    if getattr(openai_module, "_baikov_runtime_patch", False):
        return

    real_async_openai = openai_module.AsyncOpenAI

    class _ResponsesProxy:
        def __init__(self, responses: Any):
            self._responses = responses

        async def create(self, **kwargs):
            request = copy.deepcopy(kwargs)
            user_message = _last_user_message(request.get("input"))
            catalog_request = _is_company_catalog_request(user_message)
            product_request = _is_product_research_request(user_message)
            plant_request = _is_plant_protection_request(user_message) or catalog_request or product_request
            had_web_tool = bool(request.get("tools"))
            needs_research = catalog_request or product_request or had_web_tool

            if plant_request and isinstance(request.get("input"), list):
                request["input"] = list(request["input"]) + [
                    {"role": "system", "content": _field_advisor_prompt()}
                ]

            if needs_research and isinstance(request.get("input"), list):
                request["input"] = list(request["input"]) + [
                    {"role": "system", "content": _research_prompt(user_message)}
                ]
                if not request.get("tools"):
                    request["tools"] = [{"type": "web_search"}]
                    request["tool_choice"] = "required"
                    request["include"] = ["web_search_call.action.sources"]
                request["reasoning"] = {"effort": "medium"}
                request["max_output_tokens"] = max(int(request.get("max_output_tokens") or 0), 1200)

            response = await self._responses.create(**request)
            sources = _extract_sources(response) if needs_research else []

            if needs_research and not sources:
                retry = copy.deepcopy(request)
                retry["tools"] = [{"type": "web_search"}]
                retry["tool_choice"] = "required"
                retry["include"] = ["web_search_call.action.sources"]
                if isinstance(retry.get("input"), list):
                    retry["input"] = list(retry["input"]) + [{
                        "role": "system",
                        "content": (
                            "Первый поиск не дал пригодных ссылок. Повтори поиск шире без доменных ограничений. "
                            "Сначала найди официальный сайт производителя и его каталог, затем регистрационные данные и авторитетные справочники."
                        ),
                    }]
                response = await self._responses.create(**retry)
                sources = _extract_sources(response)

            if catalog_request and not had_web_tool:
                answer = str(getattr(response, "output_text", "") or "").strip()
                if sources:
                    answer = _append_sources(answer, sources)
                return _ResponseProxy(response, answer)
            return response

        def __getattr__(self, name: str):
            return getattr(self._responses, name)

    class _AsyncOpenAIProxy:
        def __init__(self, *args, **kwargs):
            self._client = real_async_openai(*args, **kwargs)
            self.responses = _ResponsesProxy(self._client.responses)

        def __getattr__(self, name: str):
            return getattr(self._client, name)

    openai_module.AsyncOpenAI = _AsyncOpenAIProxy
    openai_module._baikov_runtime_patch = True


_install_patch()
