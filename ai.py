import aiohttp
import os

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.1-8b-instruct:free"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/statnigga-bot",
    "X-Title": "StatNigga Bot",
}


async def _chat(messages: list[dict], max_tokens: int = 1024) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, json=payload, headers=HEADERS) as resp:
            resp.raise_for_status()
            data = await resp.json()
    return data["choices"][0]["message"]["content"].strip()


async def ask(question: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Отвечай коротко, грубовато, без лишних вежливостей и воды. "
                "Без приветствий, без «конечно», без «рад помочь». "
                "Только суть, можно с сарказмом."
            ),
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
            "content": (
                "Ты аналитик чатов. Тебе дадут историю переписки. "
                "Дай каждому участнику рейтинг строго в формате:\n"
                "**Имя** — краткое описание персонажа\n"
                "Cringe: X/10 | Vulgarity: X/10 | Stupidity: X/10 | Adequacy: X/10\n\n"
                "Будь честен и саркастичен. Не придумывай участников, которых нет."
            ),
        },
        {"role": "user", "content": f"История чата:\n{history}"},
    ]
    return await _chat(messages, max_tokens=1500)


async def summary(msgs: list[dict]) -> str:
    history = _format_history(msgs)
    messages = [
        {
            "role": "system",
            "content": (
                "Ты саркастичный летописец. Напиши краткое саммари переписки с разделами по темам. "
                "Каждый раздел — заголовок и 2-3 предложения с иронией. "
                "Без воды, без морали."
            ),
        },
        {"role": "user", "content": f"История чата:\n{history}"},
    ]
    return await _chat(messages, max_tokens=1200)


async def future(msgs: list[dict]) -> str:
    history = _format_history(msgs)
    messages = [
        {
            "role": "system",
            "content": (
                "Ты генератор продолжений чатов. Напиши 10-15 реплик продолжения диалога "
                "строго в формате [Имя]: сообщение. "
                "Сохраняй стиль, тематику и манеру речи каждого участника. "
                "Используй только имена из истории."
            ),
        },
        {"role": "user", "content": f"История чата:\n{history}"},
    ]
    return await _chat(messages, max_tokens=1000)
