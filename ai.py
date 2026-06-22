import asyncio
import logging
import time
import aiohttp
import os

logger = logging.getLogger(__name__)

API_URL = "https://api.vsegpt.ru/v1/chat/completions"

MODELS = [
    "openai/gpt-3.5-turbo",
    "openai/gpt-4o-mini",
    "anthropic/claude-haiku",
]

SYSTEM_PROMPT = """Ты — бот в русскоязычном групповом чате. Ты не ассистент, ты просто участник беседы.

Отвечай по ситуации. Материться и грубить можно, но не обязательно — веди себя естественно. Если к тебе обращаются по нику — отвечай адресно.

Если просят что-то сделать (рэп, историю, оценку, диалог) — врубайся и делай без лишних оговорок.

Не пиши "чем могу помочь" и не строй из себя помощника. Не читай морали без нужды.

Пиши только на русском."""


def _build_system(extra: str | None = None) -> str:
    if extra:
        return SYSTEM_PROMPT + "\n\n" + extra
    return SYSTEM_PROMPT


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('VSEGPT_API_KEY', '')}",
        "Content-Type": "application/json",
    }


# Rate limiter: 15 requests per minute
_rate_lock = asyncio.Lock()
_request_times: list[float] = []
RATE_LIMIT = 15
RATE_WINDOW = 60.0

# Per-chat cooldowns for heavy commands (seconds)
_chat_cooldowns: dict[int, float] = {}
COOLDOWN_SECONDS = 10


async def _acquire_rate_slot():
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


def check_cooldown(chat_id: int) -> float:
    last = _chat_cooldowns.get(chat_id, 0.0)
    return max(0.0, COOLDOWN_SECONDS - (time.monotonic() - last))


def set_cooldown(chat_id: int):
    _chat_cooldowns[chat_id] = time.monotonic()


async def _chat(messages: list[dict], max_tokens: int = 1024) -> str:
    await _acquire_rate_slot()

    last_error = None
    for model in MODELS:
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, json=payload, headers=_headers()) as resp:
                    if resp.status not in (200, 201):
                        body = await resp.text()
                        last_error = f"{resp.status} from {model}: {body[:300]}"
                        logger.error("api error [%s]: %s | %s", model, resp.status, body[:300])
                        continue
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"]
                    if text is None:
                        last_error = f"empty response from {model}"
                        continue
                    return text.strip()
        except Exception as e:
            last_error = str(e)
            continue

    raise RuntimeError(f"All models failed. Last error: {last_error}")


def _format_history(msgs: list[dict]) -> str:
    return "\n".join(f"[{m['username']}]: {m['text']}" for m in msgs)


async def ask(question: str, extra: str | None = None, history: list[dict] | None = None) -> str:
    system = _build_system(extra) + "\n\nОтвечай прямо, без вступлений и предисловий. Только суть."
    if history:
        history_text = _format_history(history)
        user_content = f"Последние сообщения чата:\n{history_text}\n\nВопрос: {question}"
    else:
        user_content = question
    return await _chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ])


async def rating(msgs: list[dict], extra: str | None = None) -> str:
    system = _build_system(extra) + (
        "\n\nОцени участников чата снисходительно, как будто они тебя немного раздражают но ты к ним привык. "
        "Строго в формате:\n"
        "**Имя** — одна фраза кто это такой\n"
        "Cringe: X/10 | Vulgarity: X/10 | Stupidity: X/10 | Adequacy: X/10\n\n"
        "Не придумывай участников которых нет в истории."
    )
    return await _chat([
        {"role": "system", "content": system},
        {"role": "user", "content": f"История чата:\n{_format_history(msgs)}"},
    ], max_tokens=1500)


async def summary(msgs: list[dict], extra: str | None = None) -> str:
    system = _build_system(extra) + (
        "\n\nНапиши саркастичные буллеты по темам чата. "
        "Иронизируй над тупостью происходящего, как будто тебе лень это читать но ты всё равно прокомментировал. "
        "Без воды и выводов."
    )
    return await _chat([
        {"role": "system", "content": system},
        {"role": "user", "content": f"История чата:\n{_format_history(msgs)}"},
    ], max_tokens=1200)


async def future(msgs: list[dict], extra: str | None = None) -> str:
    system = _build_system(extra) + (
        "\n\nПродолжи диалог, точно копируя структуру и ритм чата — как люди реально пишут. "
        "10-15 реплик строго в формате [Имя]: сообщение. "
        "Используй только имена из истории, сохраняй их словарный запас и манеру."
    )
    return await _chat([
        {"role": "system", "content": system},
        {"role": "user", "content": f"История чата:\n{_format_history(msgs)}"},
    ], max_tokens=1000)
