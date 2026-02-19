from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  # ensures models are registered with Base
from app.core.config import settings
from app.core.db import Base, engine
from app.core.errors import AppError
from app.routers import projects, slides, templates

app = FastAPI(
    title="Carrosseis Infinitos API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Ensure tables exist on startup (simple MVP approach)
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(slides.router)
app.include_router(templates.router)

app.mount("/data", StaticFiles(directory="data"), name="data")


@app.exception_handler(AppError)
async def app_error_handler(_, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple health probe used by frontend/devops."""
    return {
        "status": "ok",
        "environment": settings.environment,
    }
