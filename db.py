import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "messages.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id   INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                username  TEXT,
                text      TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chat ON messages(chat_id, timestamp)")
        await db.commit()


async def save_message(chat_id: int, user_id: int, username: str | None, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (chat_id, user_id, username, text) VALUES (?, ?, ?, ?)",
            (chat_id, user_id, username or str(user_id), text),
        )
        await db.commit()


async def get_last_messages(chat_id: int, limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT username, text, timestamp
            FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in reversed(rows)]
