import os
import asyncpg

from contextlib import asynccontextmanager
from fastapi import FastAPI
from .routes import router

DB_DSN = os.getenv(
    "DATABASE_URL", "postgresql://pair:pair@localhost:5432/pair_takehome"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=2, max_size=10)
    yield
    await app.state.pool.close()


app = FastAPI(title="PAIR Takehome API", lifespan=lifespan)
app.include_router(router)
