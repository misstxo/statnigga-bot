# StatNigga Bot

Telegram-бот для группового чата с командами `/ask`, `/rating`, `/summary`, `/future`.

## Локальный запуск

```bash
pip install -r requirements.txt

export BOT_TOKEN=ваш_токен
export OPENROUTER_API_KEY=ваш_ключ
export WEBHOOK_URL=https://ваш-домен.onrender.com

python bot.py
```

## Деплой на Render

### 1. Создай Web Service

- Перейди на [render.com](https://render.com) → **New → Web Service**
- Подключи репозиторий с кодом

### 2. Настройки сервиса

| Поле | Значение |
|------|----------|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python bot.py` |

### 3. Environment Variables

Добавь в разделе **Environment**:

| Ключ | Значение |
|------|----------|
| `BOT_TOKEN` | Токен от @BotFather |
| `OPENROUTER_API_KEY` | Ключ с [openrouter.ai](https://openrouter.ai) |
| `WEBHOOK_URL` | URL вида `https://your-app.onrender.com` (без слеша в конце) |
| `PORT` | `10000` (Render выставляет автоматически) |

> `WEBHOOK_URL` — это именно URL твоего Render-сервиса. Его можно скопировать после деплоя.

### 4. Деплой

Нажми **Create Web Service**. После деплоя бот сам зарегистрирует вебхук.

### 5. Проверка

Открой в браузере `https://your-app.onrender.com/webhook` — должен вернуться HTTP 405 (Method Not Allowed).  
Это значит, что сервер работает и слушает вебхук.

---

## Структура проекта

```
bot.py          — точка входа, настройка webhook + aiohttp
handlers.py     — обработчики команд и сохранение сообщений
db.py           — инициализация SQLite, запись/чтение сообщений
ai.py           — запросы к OpenRouter (ask / rating / summary / future)
requirements.txt
README.md
```

## Команды

| Команда | Описание |
|---------|----------|
| `/ask [вопрос]` | Короткий грубоватый ответ от ИИ |
| `/rating` | Рейтинг участников по последним 100 сообщениям (Cringe / Vulgarity / Stupidity / Adequacy) |
| `/summary` | Саркастичное саммари последних 100 сообщений по темам |
| `/future` | Продолжение диалога в стиле участников |

## Заметки

- SQLite-файл `messages.db` создаётся в рабочей директории при старте.  
  На Render диск эфемерный — данные теряются при перезапуске.  
  Для персистентности подключи Render Disk или используй внешнюю БД (например, Turso / Supabase).
- Бот слушает **все** текстовые сообщения в чате и сохраняет их в БД.
- Для работы в группе убедись, что бот добавлен в группу с правами чтения сообщений.  
  В приватных группах/супергруппах может потребоваться включить **Privacy Mode Off** через @BotFather.
