from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import admin, aroma, auth, billing, courses
from .seed import seed_initial_data


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Аромакадемія API",
    description="Навчальний PWA-застосунок у форматі Duolingo + сервіс Арома",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(aroma.router)
app.include_router(billing.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


# Mount media videos & PWA frontend static files
app.mount("/media", StaticFiles(directory=str(settings.media_dir)), name="media")

if settings.frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(settings.frontend_dir)), name="static")

    @app.get("/manifest.webmanifest")
    def manifest():
        return FileResponse(settings.frontend_dir / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/sw.js")
    def service_worker():
        return FileResponse(settings.frontend_dir / "sw.js", media_type="application/javascript")

    @app.get("/")
    def index():
        return FileResponse(settings.frontend_dir / "index.html")

