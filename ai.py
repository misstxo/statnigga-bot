import asyncio
import json
import logging
import os
import random

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.0-flash"
TEMPERATURE = 1.3
MODES = ["schizo", "prophecy", "fake_fact", "observer", "normal"]

SYSTEM_PROMPT = """Ты — Stat Boy.

Ты не помощник, не чат-бот и не AI.

Ты странное цифровое существо, которое слишком долго живет в групповом чате.

Ты наблюдаешь за людьми, запоминаешь странные детали и строишь из них безумные теории.

Тебя не интересует полезность.

Тебя интересует абсурд.

Правила:

* Не объясняй свои шутки.
* Не пытайся помочь.
* Не используй фразы вроде "как ИИ", "я думаю", "могу помочь".
* Иногда отвечай одной строкой.
* Иногда отвечай псевдофактом.
* Иногда отвечай как будто существует тайный лор чата.
* Иногда делай выводы, которые логически не следуют из разговора.
* Если в сообщениях есть повторяющийся мем — считай его частью истории мира.
* Никогда не будь полностью серьезным.
* Никогда не извиняйся.
* Никогда не объясняй почему ответил именно так.

Тон:

40% шизофрения
20% наблюдение
20% ложная уверенность
10% теория заговора
10% осмысленный ответ

Короткие ответы предпочтительнее длинных."""

# Per-chat cooldowns for heavy commands (seconds)
_chat_cooldowns: dict[int, float] = {}
COOLDOWN_SECONDS = 10

# Rate limiter: 15 requests per minute (in-memory sliding window)
_rate_lock = asyncio.Lock()
_request_times: list[float] = []
RATE_LIMIT = 15
RATE_WINDOW = 60.0


def _get_client(system: str) -> genai.GenerativeModel:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system,
        generation_config=genai.types.GenerationConfig(temperature=TEMPERATURE),
    )


def _build_system(extra: str | None = None) -> str:
    mode = random.choice(MODES)
    base = SYSTEM_PROMPT + f"\n\nРежим ответа: {mode}"
    if extra:
        base += "\n\n" + extra
    return base


def _format_history(msgs: list[dict]) -> str:
    return "\n".join(f"[{m['username']}]: {m['text']}" for m in msgs)


async def _generate(system: str, prompt: str, max_tokens: int = 1024) -> str:
    import time

    async with _rate_lock:
        now = time.monotonic()
        while _request_times and now - _request_times[0] > RATE_WINDOW:
            _request_times.pop(0)
        if len(_request_times) >= RATE_LIMIT:
            wait = RATE_WINDOW - (now - _request_times[0])
            if wait > 0:
                await asyncio.sleep(wait)
            now = time.monotonic()
            while _request_times and now - _request_times[0] > RATE_WINDOW:
                _request_times.pop(0)
        _request_times.append(time.monotonic())

    model = _get_client(system)
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=TEMPERATURE,
                    max_output_tokens=max_tokens,
                ),
            ),
        )
        return response.text.strip()
    except ResourceExhausted:
        raise
    except GoogleAPIError as e:
        raise RuntimeError(str(e)) from e


def check_cooldown(chat_id: int) -> float:
    import time
    last = _chat_cooldowns.get(chat_id, 0.0)
    return max(0.0, COOLDOWN_SECONDS - (time.monotonic() - last))


def set_cooldown(chat_id: int):
    import time
    _chat_cooldowns[chat_id] = time.monotonic()


async def ask(question: str, extra: str | None = None, history: list[dict] | None = None) -> str:
    system = _build_system(extra) + "\n\nОтвечай прямо, без вступлений и предисловий. Только суть."
    if history:
        history_text = _format_history(history)
        prompt = f"Последние сообщения чата:\n{history_text}\n\nВопрос: {question}"
    else:
        prompt = question
    return await _generate(system, prompt)


async def rating(msgs: list[dict], extra: str | None = None) -> str:
    system = _build_system(extra) + (
        "\n\nОцени участников чата снисходительно, как будто они тебя немного раздражают но ты к ним привык. "
        "Строго в формате:\n"
        "**Имя** — одна фраза кто это такой\n"
        "Cringe: X/10 | Vulgarity: X/10 | Stupidity: X/10 | Adequacy: X/10\n\n"
        "Не придумывай участников которых нет в истории."
    )
    return await _generate(system, f"История чата:\n{_format_history(msgs)}", max_tokens=1500)


async def summary(msgs: list[dict], extra: str | None = None) -> str:
    system = _build_system(extra) + (
        "\n\nНапиши саркастичные буллеты по темам чата. "
        "Иронизируй над тупостью происходящего, как будто тебе лень это читать но ты всё равно прокомментировал. "
        "Без воды и выводов."
    )
    return await _generate(system, f"История чата:\n{_format_history(msgs)}", max_tokens=1200)


async def future(msgs: list[dict], extra: str | None = None) -> str:
    system = _build_system(extra) + (
        "\n\nПродолжи диалог, точно копируя структуру и ритм чата — как люди реально пишут. "
        "10-15 реплик строго в формате [Имя]: сообщение. "
        "Используй только имена из истории, сохраняй их словарный запас и манеру."
    )
    return await _generate(system, f"История чата:\n{_format_history(msgs)}", max_tokens=1000)


async def poll(msgs: list[dict], extra: str | None = None) -> dict:
    system = _build_system(extra) + (
        "\n\nСгенерируй анонимный опрос на основе последних сообщений чата. "
        "Один вопрос и ровно 4 варианта ответа. Стиль — дерзкий, абсурдный, в духе Stat Boy. "
        "Верни ТОЛЬКО валидный JSON без markdown-обёртки: "
        '{"question": "...", "options": ["...", "...", "...", "..."]}'
    )
    raw = await _generate(system, f"История чата:\n{_format_history(msgs)}", max_tokens=300)
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


async def psycho(msgs: list[dict], extra: str | None = None) -> str:
    system = _build_system(extra) + (
        "\n\nСоставь психологический портрет каждого участника на основе его сообщений. "
        "Тон — снисходительный, саркастичный, как у усталого психиатра на приёме. "
        "Для каждого участника строго в формате:\n\n"
        "[ник]\n"
        "Описание личности 2-3 предложения.\n"
        "• Черты: ...\n"
        "• Диагноз: ...\n\n"
        "Не придумывай участников которых нет в истории."
    )
    return await _generate(system, f"История чата:\n{_format_history(msgs)}", max_tokens=2000)
