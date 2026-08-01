import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Must be set before trust_governance_engine.config (and anything importing it) is
# loaded for the first time, since Settings reads the environment at
# import-time.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_governance.db")
os.environ.setdefault("OTP_DEV_MODE_EXPOSE_CODE", "true")

from trust_governance_engine.db.models import Base  # noqa: E402
from trust_governance_engine.db.session import engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    db_path = Path("./test_governance.db")
    if db_path.exists():
        db_path.unlink()

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    yield
