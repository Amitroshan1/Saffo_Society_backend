"""Quick DB connection check.

Usage (from Backend/ with venv active):
    python check_db.py
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from Core.config import settings


async def main() -> None:
    print("Checking:", settings.DATABASE_URL.split("@")[-1])
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SELECT version()"))).scalar()
            db_name = (await conn.execute(text("SELECT current_database()"))).scalar()
        print("CONNECTED: YES")
        print("Database:", db_name)
        print("PostgreSQL:", (version or "").split(",")[0])
    except Exception as exc:
        print("CONNECTED: NO")
        print("Error:", type(exc).__name__, "-", exc)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
