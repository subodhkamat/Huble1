
import asyncio

from sqlalchemy import text
from database import engine


async def main():
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            print("Database connection successful:", result.scalar_one())
    except Exception as error:
        print("Database connection failed:", repr(error))
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())