
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

BASE_DIR = Path(__file__).resolve().parent

# Load the backend's .env file explicitly.
load_dotenv(BASE_DIR / ".env", override=True)

# Use SQLite for local development.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{(BASE_DIR / 'buildai.db').as_posix()}",
)

DATABASE_URL = DATABASE_URL.strip().strip('"\'')

if not DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    raise RuntimeError(
        "SQLite is required for this setup. "
        "Set DATABASE_URL=sqlite+aiosqlite:///./buildai.db in backend/.env"
    )

# A relative path like ./buildai.db depends on the directory uvicorn is started
# from; a different working directory silently creates an empty DB with no tables.
_db_path = DATABASE_URL.removeprefix("sqlite+aiosqlite:///")
if _db_path and not Path(_db_path).is_absolute() and _db_path != ":memory:":
    DATABASE_URL = f"sqlite+aiosqlite:///{(BASE_DIR / _db_path).resolve().as_posix()}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session