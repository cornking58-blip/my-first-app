import base64
import os
import re
from typing import Optional

from fastapi import HTTPException
from openai import AsyncOpenAI


MAX_PHOTO_BYTES = 6 * 1024 * 1024
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

PHOTO_DIAGNOSIS_SYSTEM_PROMPT = """
Ты — опытный агроном-практик bAIkov. Анализируй фотографию только в контексте сельского хозяйства и защиты растений.

Правила:
1. Не выдавай предположение за окончательный диагноз по одной фотографии.
2. Сначала опиши только те признаки, которые реально видны на снимке.
3. Затем дай 1–3 наиболее вероятные причины: болезнь, вредитель, дефицит питания, погодный стресс, химический ожог или другая причина.
4. Для каждой версии укажи, какие признаки говорят в её пользу и что ей противоречит.
5. Обязательно напиши, что проверить в поле: культура, фаза, распространённость, сторона листа, корни, стебель, погода и недавние обработки.
6. Не выдумывай торговые препараты, нормы и регистрации. Если данных недостаточно — так и скажи.
7. Говори простыми словами, по-свойски, но профессионально. Уместен лёгкий юмор, без балагана.
8. Ответ должен быть практичным и структурным.

Формат ответа:
Что видно
Вероятные причины
Что проверить в поле
Что делать сейчас
Что ещё сфотографировать

Если на фото нет растения, вредителя, болезни, сорняка или другого агрономического объекта, честно скажи, что по этому снимку агрономическую диагностику выполнить нельзя.
""".strip()


def validate_photo_data_url(image_data_url: str) -> str:
    value = (image_data_url or "").strip()
    match = re.fullmatch(
        r"data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)",
        value,
    )
    if not match:
        raise HTTPException(status_code=400, detail="Некорректный формат фотографии")

    mime_type = match.group(1).lower()
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются фотографии JPEG, PNG и WEBP",
        )

    payload = re.sub(r"\s+", "", match.group(2))
    try:
        decoded = base64.b64decode(payload, validate=True)
    except Exception as error:
        raise HTTPException(status_code=400, detail="Не удалось прочитать фотографию") from error

    if not decoded:
        raise HTTPException(status_code=400, detail="Фотография пустая")
    if len(decoded) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Фотография слишком большая. Максимум 6 МБ после сжатия.",
        )
    return f"data:{mime_type};base64,{payload}"


async def analyze_photo_with_ai(
    image_data_url: str,
    question: Optional[str] = None,
) -> str:
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ИИ временно не настроен")

    normalized_image = validate_photo_data_url(image_data_url)
    user_text = (question or "").strip()
    if not user_text:
        user_text = (
            "Проанализируй фотографию как агроном. Определи видимые симптомы, "
            "назови наиболее вероятные причины и дай практический план проверки в поле."
        )

    client_options = {"api_key": api_key}
    base_url = (os.environ.get("AI_BASE_URL") or "").strip()
    if base_url:
        client_options["base_url"] = base_url

    client = AsyncOpenAI(**client_options)
    try:
        response = await client.responses.create(
            model=(
                os.environ.get("AI_VISION_MODEL")
                or os.environ.get("AI_MODEL")
                or "gpt-5.6"
            ).strip(),
            input=[
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": PHOTO_DIAGNOSIS_SYSTEM_PROMPT}
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_text[:2000]},
                        {
                            "type": "input_image",
                            "image_url": normalized_image,
                            "detail": "high",
                        },
                    ],
                },
            ],
            reasoning={"effort": "low"},
            max_output_tokens=1800,
            extra_body={"prompt_cache_key": "baikov:photo-diagnosis:v1"},
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Не удалось проанализировать фотографию. Попробуйте другой снимок.",
        ) from error

    answer = getattr(response, "output_text", None)
    if not answer or not answer.strip():
        raise HTTPException(status_code=502, detail="ИИ не смог разобрать фотографию")
    return answer.strip()
