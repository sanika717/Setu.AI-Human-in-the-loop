import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "app"
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_backend.db")
os.environ.setdefault("TESTING", "1")
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.db.models import Base
from app.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    db_path = Path("./test_backend.db")
    if db_path.exists():
        db_path.unlink()

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    yield
