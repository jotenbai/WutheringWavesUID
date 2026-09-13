from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router
from .config import ASSET_VERSION, PUBLIC_PREFIX, SESSION_HTTPS_ONLY, SESSION_SECRET, STATIC_DIR, ensure_dirs
from .routes import files_router, router as api_router
from .submit_routes import router as submit_router

ensure_dirs()

app = FastAPI(title="Shorekeeper Gallery", version="0.3.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="gallery_session",
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
    max_age=60 * 60 * 24 * 30,
)
app.include_router(auth_router)
app.include_router(api_router)
app.include_router(submit_router)
app.include_router(files_router)

app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


def _index_html() -> str:
    raw = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    prefix = PUBLIC_PREFIX or ""
    base = (prefix + "/") if prefix else "/"
    return (
        raw.replace("__GALLERY_BASE_HREF__", base)
        .replace("__GALLERY_PUBLIC_PREFIX__", prefix)
        .replace("__GALLERY_ASSET_VERSION__", ASSET_VERSION)
    )


@app.get("/")
def index():
    return HTMLResponse(_index_html())


@app.get("/favicon.ico")
def favicon():
    ico = STATIC_DIR / "favicon.ico"
    if ico.is_file():
        return FileResponse(ico)
    return Response(status_code=204)


@app.get("/char/{char_id}")
def spa_char(char_id: str):
    return HTMLResponse(_index_html())


@app.get("/submit")
@app.get("/me")
@app.get("/review")
def spa_app_pages():
    return HTMLResponse(_index_html())
