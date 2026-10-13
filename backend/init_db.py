
import asyncio

from sqlalchemy import text

from database import Base, engine
import db_model  # Registers User, Project, and AuthSession


async def init_db():
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' ORDER BY name"
                )
            )
            tables = [row[0] for row in result.fetchall()]

        print("Database initialized successfully.")
        print("Tables found:", tables)

        expected = {"users", "projects", "auth_sessions"}
        missing = expected - set(tables)

        if missing:
            raise RuntimeError(f"Missing tables: {sorted(missing)}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())