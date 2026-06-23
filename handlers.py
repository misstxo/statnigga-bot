import json
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
import ai
import db

router = Router()
logger = logging.getLogger(__name__)

_OVERLOAD = "перегружен, попробуй позже"


def _err(cmd: str, e: Exception):
    logger.error("%s error: %s", cmd, e)


@router.message(Command("ask"))
async def cmd_ask(message: Message):
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply("Вопрос где?")
        return
    extra = await db.get_instructions(message.chat.id)
    history = await db.get_last_messages(message.chat.id, 30)
    try:
        answer = await ai.ask(parts[1].strip(), extra=extra, history=history)
    except Exception as e:
        _err("ask", e); await message.reply(_OVERLOAD); return
    await message.reply(answer, parse_mode="HTML")


@router.message(Command("rating"))
async def cmd_rating(message: Message):
    remaining = ai.check_cooldown(message.chat.id)
    if remaining:
        await message.reply(f"Подожди ещё {remaining:.0f} сек.")
        return
    msgs = await db.get_last_messages(message.chat.id, 100)
    if not msgs:
        await message.reply("Нет сообщений для анализа.")
        return
    ai.set_cooldown(message.chat.id)
    extra = await db.get_instructions(message.chat.id)
    try:
        result = await ai.rating(msgs, extra=extra)
    except Exception as e:
        _err("rating", e); await message.reply(_OVERLOAD); return
    await message.reply(result, parse_mode="HTML")


@router.message(Command("summary"))
async def cmd_summary(message: Message):
    remaining = ai.check_cooldown(message.chat.id)
    if remaining:
        await message.reply(f"Подожди ещё {remaining:.0f} сек.")
        return
    msgs = await db.get_last_messages(message.chat.id, 100)
    if not msgs:
        await message.reply("Нет сообщений для саммари.")
        return
    ai.set_cooldown(message.chat.id)
    extra = await db.get_instructions(message.chat.id)
    try:
        result = await ai.summary(msgs, extra=extra)
    except Exception as e:
        _err("summary", e); await message.reply(_OVERLOAD); return
    await message.reply(result, parse_mode="HTML")


@router.message(Command("future"))
async def cmd_future(message: Message):
    remaining = ai.check_cooldown(message.chat.id)
    if remaining:
        await message.reply(f"Подожди ещё {remaining:.0f} сек.")
        return
    msgs = await db.get_last_messages(message.chat.id, 100)
    if not msgs:
        await message.reply("Нет сообщений для предсказания.")
        return
    ai.set_cooldown(message.chat.id)
    extra = await db.get_instructions(message.chat.id)
    try:
        result = await ai.future(msgs, extra=extra)
    except Exception as e:
        _err("future", e); await message.reply(_OVERLOAD); return
    await message.reply(result, parse_mode="HTML")


@router.message(Command("poll"))
async def cmd_poll(message: Message, bot: Bot):
    remaining = ai.check_cooldown(message.chat.id)
    if remaining:
        await message.reply(f"Подожди ещё {remaining:.0f} сек.")
        return
    msgs = await db.get_last_messages(message.chat.id, 30)
    if not msgs:
        await message.reply("Нет сообщений для опроса.")
        return
    ai.set_cooldown(message.chat.id)
    extra = await db.get_instructions(message.chat.id)
    try:
        data = await ai.poll(msgs, extra=extra)
        question = data["question"]
        options = data["options"]
    except json.JSONDecodeError as e:
        _err("poll json", e); await message.reply("не смог придумать опрос, попробуй позже"); return
    except Exception as e:
        _err("poll", e); await message.reply(_OVERLOAD); return
    await bot.send_poll(
        chat_id=message.chat.id,
        question=question[:300],
        options=[o[:100] for o in options[:10]],
        is_anonymous=True,
    )


@router.message(Command("psycho"))
async def cmd_psycho(message: Message):
    remaining = ai.check_cooldown(message.chat.id)
    if remaining:
        await message.reply(f"Подожди ещё {remaining:.0f} сек.")
        return
    msgs = await db.get_last_messages(message.chat.id, 100)
    if not msgs:
        await message.reply("Нет сообщений для анализа.")
        return
    ai.set_cooldown(message.chat.id)
    extra = await db.get_instructions(message.chat.id)
    try:
        result = await ai.psycho(msgs, extra=extra)
    except Exception as e:
        _err("psycho", e); await message.reply(_OVERLOAD); return
    await message.reply(result, parse_mode="HTML")


@router.message(Command("instructions"))
async def cmd_instructions(message: Message):
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        current = await db.get_instructions(message.chat.id)
        if current:
            await message.reply(f"Текущие инструкции:\n\n{current}")
        else:
            await message.reply("Кастомных инструкций нет.")
        return
    await db.set_instructions(message.chat.id, parts[1].strip())
    await message.reply("Инструкции сохранены.")


@router.message(Command("clearinstructions"))
async def cmd_clearinstructions(message: Message):
    await db.clear_instructions(message.chat.id)
    await message.reply("Инструкции очищены.")


@router.message()
async def store_message(message: Message):
    if not message.text:
        return
    username = message.from_user.username or message.from_user.full_name or str(message.from_user.id)
    await db.save_message(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        username=username,
        text=message.text,
    )
