from __future__ import annotations

from pathlib import Path

import asyncpg
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import get_session
from app.main import app

TEST_DB_NAME = "pair_takehome_test"
ADMIN_DSN = "postgresql://pair:pair@localhost:5432/postgres"
TEST_DSN = f"postgresql+asyncpg://pair:pair@localhost:5432/{TEST_DB_NAME}"
RAW_DSN = f"postgresql://pair:pair@localhost:5432/{TEST_DB_NAME}"

DB_DIR = Path(__file__).resolve().parent.parent.parent / "db"


@pytest_asyncio.fixture(scope="session")
async def test_database():
    admin_conn = await asyncpg.connect(ADMIN_DSN)
    await admin_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
    await admin_conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    await admin_conn.close()

    conn = await asyncpg.connect(RAW_DSN)
    await conn.execute((DB_DIR / "00-schema.sql").read_text())
    await conn.execute((DB_DIR / "01-seed.sql").read_text())
    await conn.close()

    yield TEST_DSN

    admin_conn = await asyncpg.connect(ADMIN_DSN)
    await admin_conn.execute(
        "SELECT pg_terminate_backend(pid) "
        "FROM pg_stat_activity "
        f"WHERE datname = '{TEST_DB_NAME}' AND pid != pg_backend_pid()"
    )
    await admin_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
    await admin_conn.close()


@pytest_asyncio.fixture
async def client(test_database):
    engine = create_async_engine(test_database)
    conn = await engine.connect()
    tx = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)

    async def override():
        yield session

    app.dependency_overrides[get_session] = override

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    await tx.rollback()
    await session.close()
    await conn.close()
    await engine.dispose()
    app.dependency_overrides.clear()
