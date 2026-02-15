from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import engine
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="PAIR Takehome API", lifespan=lifespan)
app.include_router(router)
