import asyncio
import logging
import time
import aiohttp
import os

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/statnigga-bot",
        "X-Title": "StatNigga Bot",
    }

# Rate limiter: 15 requests per minute
_rate_lock = asyncio.Lock()
_request_times: list[float] = []
RATE_LIMIT = 15
RATE_WINDOW = 60.0

# Per-chat cooldowns for heavy commands (seconds)
_chat_cooldowns: dict[int, float] = {}
COOLDOWN_SECONDS = 10

BASE_SYSTEM = """Ты — бот в русскоязычном чате. Отвечай коротко и по делу.
Материться можно, грубить можно, но не обязательно — веди себя естественно по ситуации.
Ты знаешь что ты ИИ и иногда сам это упоминаешь.
Не читай морали без необходимости, но и не пытайся казаться "плохим парнем" специально.
Отвечай на русском."""


async def _acquire_rate_slot():
    async with _rate_lock:
        now = time.monotonic()
        # Drop timestamps older than the window
        while _request_times and now - _request_times[0] > RATE_WINDOW:
            _request_times.pop(0)

        if len(_request_times) >= RATE_LIMIT:
            wait = RATE_WINDOW - (now - _request_times[0])
            if wait > 0:
                await asyncio.sleep(wait)
            # Re-clean after sleep
            now = time.monotonic()
            while _request_times and now - _request_times[0] > RATE_WINDOW:
                _request_times.pop(0)

        _request_times.append(time.monotonic())


def check_cooldown(chat_id: int) -> float:
    """Returns remaining cooldown seconds, or 0 if ready."""
    last = _chat_cooldowns.get(chat_id, 0.0)
    remaining = COOLDOWN_SECONDS - (time.monotonic() - last)
    return max(0.0, remaining)


def set_cooldown(chat_id: int):
    _chat_cooldowns[chat_id] = time.monotonic()


async def _chat(messages: list[dict], max_tokens: int = 1024) -> str:
    await _acquire_rate_slot()

    last_error = None
    for model in MODELS:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    OPENROUTER_URL, json=payload, headers=_headers()
                ) as resp:
                    if resp.status not in (200, 201):
                        body = await resp.text()
                        last_error = f"{resp.status} from {model}: {body[:300]}"
                        logger.error("openrouter error [%s]: %s | body: %s", model, resp.status, body[:300])
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


async def ask(question: str) -> str:
    messages = [
        {
            "role": "system",
            "content": BASE_SYSTEM + "\n\nДля /ask: отвечай прямо и грубо, без вступлений. "
                "Никаких «конечно», «рад помочь», никаких предисловий. Только суть.",
        },
        {"role": "user", "content": question},
    ]
    return await _chat(messages)


def _format_history(msgs: list[dict]) -> str:
    return "\n".join(f"[{m['username']}]: {m['text']}" for m in msgs)


async def rating(msgs: list[dict]) -> str:
    history = _format_history(msgs)
    messages = [
        {
            "role": "system",
            "content": BASE_SYSTEM + "\n\nДля /rating: оцениваешь участников снисходительно, "
                "как будто они тебя немного раздражают но ты к ним привык. "
                "Строго в формате:\n"
                "**Имя** — одна фраза кто это такой\n"
                "Cringe: X/10 | Vulgarity: X/10 | Stupidity: X/10 | Adequacy: X/10\n\n"
                "Не придумывай участников которых нет в истории.",
        },
        {"role": "user", "content": f"История чата:\n{history}"},
    ]
    return await _chat(messages, max_tokens=1500)


async def summary(msgs: list[dict]) -> str:
    history = _format_history(msgs)
    messages = [
        {
            "role": "system",
            "content": BASE_SYSTEM + "\n\nДля /summary: пиши саркастичные буллеты по темам, "
                "иронизируй над тупостью происходящего. "
                "Как будто тебе лень это всё читать, но ты всё равно прокомментировал. "
                "Без воды, без морали, без выводов.",
        },
        {"role": "user", "content": f"История чата:\n{history}"},
    ]
    return await _chat(messages, max_tokens=1200)


async def future(msgs: list[dict]) -> str:
    history = _format_history(msgs)
    messages = [
        {
            "role": "system",
            "content": BASE_SYSTEM + "\n\nДля /future: точно копируй структуру и ритм чата — "
                "как люди реально пишут, не как должны писать. "
                "10-15 реплик строго в формате [Имя]: сообщение. "
                "Используй только имена из истории, сохраняй их словарный запас и манеру.",
        },
        {"role": "user", "content": f"История чата:\n{history}"},
    ]
    return await _chat(messages, max_tokens=1000)
