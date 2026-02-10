from contextlib import asynccontextmanager

import dotenv
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends

import api
from deps import SettingsMarker, DatabaseMarker
from settings import settings

dotenv.load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def register_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title="Bet API",
        version="0.0.1",
        description="API for betting service",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.include_router(api.router, prefix="/api")

    app.dependency_overrides.update(
        {
            SettingsMarker: lambda: settings,
        }
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = register_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
