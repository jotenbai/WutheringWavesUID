from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _path(env_key: str, default: Path) -> Path:
    raw = os.getenv(env_key)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (_ROOT / p).resolve()


def _csv_ids(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


DATA_DIR = _path("GALLERY_DATA_DIR", _ROOT / "data")
PUBLISHED_DIR = DATA_DIR / "published"
PENDING_DIR = DATA_DIR / "pending"

HOST = os.getenv("GALLERY_HOST", "127.0.0.1")
PORT = int(os.getenv("GALLERY_PORT", "8787"))
PUBLIC_PREFIX = os.getenv("GALLERY_PUBLIC_PREFIX", "").rstrip("/") or ""

DEFAULT_SUBMITTER = os.getenv("GALLERY_DEFAULT_SUBMITTER", "jo")
DEFAULT_REVIEWER = os.getenv("GALLERY_DEFAULT_REVIEWER", "jo")
ASSET_VERSION = os.getenv("GALLERY_ASSET_VERSION", "32")

_DEFAULT_OFFICIAL = Path.home() / "gsuid_core/data/WutheringWavesUID/resource/role_pile"
OFFICIAL_PILE_DIR = _path("GALLERY_OFFICIAL_PILE_DIR", _DEFAULT_OFFICIAL)

STATIC_DIR = _ROOT / "static"

# --- P1 auth ---
GSCORE_DB = _path(
    "GALLERY_GSCORE_DB",
    Path.home() / "gsuid_core/data/GsData.db",
)
GSCORE_CONFIG = _path(
    "GALLERY_GSCORE_CONFIG",
    Path.home() / "gsuid_core/data/config.json",
)

DISCORD_CLIENT_ID = (os.getenv("DISCORD_OAUTH_CLIENT_ID") or "").strip()
DISCORD_CLIENT_SECRET = (os.getenv("DISCORD_OAUTH_CLIENT_SECRET") or "").strip()
# 完整回调 URL，例如 https://core.jotenbai.moe/gallery/auth/callback
DISCORD_REDIRECT_URI = (os.getenv("DISCORD_OAUTH_REDIRECT_URI") or "").strip()

SESSION_SECRET = (os.getenv("GALLERY_SESSION_SECRET") or "").strip() or secrets.token_hex(32)
SESSION_HTTPS_ONLY = os.getenv("GALLERY_SESSION_HTTPS_ONLY", "1").strip() not in (
    "0",
    "false",
    "False",
)


def oauth_configured() -> bool:
    return bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and DISCORD_REDIRECT_URI)


def ensure_dirs() -> None:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
