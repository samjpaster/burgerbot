import aiosqlite

DB_PATH = "burgers.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_burgers (
                burger_id INTEGER PRIMARY KEY,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requested_burgers (
                burger_id INTEGER PRIMARY KEY,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_posted_ids(table: str) -> set[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(f"SELECT burger_id FROM {table}")
        rows = await cursor.fetchall()
        return {row[0] for row in rows}

async def mark_posted(table: str, burger_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT OR IGNORE INTO {table} (burger_id) VALUES (?)", (burger_id,)
        )
        await db.commit()

async def get_posted_count(table: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
        row = await cursor.fetchone()
        return row[0] if row else 0

async def reset_pool(table: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"DELETE FROM {table}")
        await db.commit()
