"""Discord OAuth + 会话身份（游客 / 「守岸人」用户 / 管理员）。"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from .config import (
    DISCORD_CLIENT_ID,
    DISCORD_CLIENT_SECRET,
    DISCORD_REDIRECT_URI,
    GSCORE_CONFIG,
    PUBLIC_PREFIX,
    oauth_configured,
)
from .wavesbind import lookup_waves_bind

router = APIRouter(tags=["auth"])

DISCORD_AUTHORIZE = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN = "https://discord.com/api/oauth2/token"
DISCORD_ME = "https://discord.com/api/users/@me"

SESSION_USER_KEY = "gallery_user"
OAUTH_STATE_KEY = "oauth_state"
# 管理员名单缓存（秒）
_admin_cache: tuple[float, set[str]] = (0.0, set())
_ADMIN_TTL = 60.0


def _load_gscore_ids(*keys: str) -> set[str]:
    path: Path = GSCORE_CONFIG
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    out: set[str] = set()
    for key in keys:
        val = data.get(key) or []
        if isinstance(val, list):
            out.update(str(x).strip() for x in val if str(x).strip())
        elif isinstance(val, str) and val.strip():
            out.add(val.strip())
    return out


def _load_gscore_staff_ids() -> set[str]:
    """A1：gscore config.json 的 masters + superusers。"""
    return _load_gscore_ids("masters", "superusers")


_master_cache: tuple[float, set[str]] = (0.0, set())


def master_ids() -> set[str]:
    """仅 gscore masters（主人）；覆盖已有图号仅主人可做。"""
    global _master_cache
    now = time.time()
    ts, cached = _master_cache
    if now - ts < _ADMIN_TTL and cached:
        return cached
    ids = _load_gscore_ids("masters")
    _master_cache = (now, ids)
    return ids


def admin_ids() -> set[str]:
    """图集管理员完全等同于 gscore config.json 的 masters + superusers，实现全生态同权。"""
    global _admin_cache
    now = time.time()
    ts, cached = _admin_cache
    if now - ts < _ADMIN_TTL and cached:
        return cached
    staff = _load_gscore_staff_ids()
    _admin_cache = (now, staff)
    return staff


@dataclass
class GalleryUser:
    id: str
    username: str
    global_name: str | None
    avatar: str | None
    has_bind: bool
    is_admin: bool
    is_master: bool = False
    uid: str | None = None

    @property
    def display_name(self) -> str:
        return (self.global_name or self.username or self.id).strip()

    @property
    def can_submit(self) -> bool:
        return self.has_bind or self.is_admin

    def to_public(self) -> dict[str, Any]:
        role = "guest"
        if self.is_admin:
            role = "admin"
        elif self.has_bind:
            role = "user"
        return {
            "id": self.id,
            "username": self.username,
            "global_name": self.global_name,
            "display_name": self.display_name,
            "avatar": self.avatar,
            "avatar_url": (
                f"https://cdn.discordapp.com/avatars/{self.id}/{self.avatar}.png"
                if self.avatar
                else None
            ),
            "has_bind": self.has_bind,
            "is_admin": self.is_admin,
            "is_master": self.is_master,
            "can_submit": self.can_submit,
            "role": role,
            "uid": self.uid,
        }


def user_from_session(data: dict | None) -> GalleryUser | None:
    if not data or not data.get("id"):
        return None
    uid = str(data["id"])
    bind = lookup_waves_bind(uid)
    is_admin = uid in admin_ids()
    is_master = uid in master_ids()
    return GalleryUser(
        id=uid,
        username=str(data.get("username") or ""),
        global_name=data.get("global_name"),
        avatar=data.get("avatar"),
        has_bind=bind is not None,
        is_admin=is_admin,
        is_master=is_master,
        uid=bind.uid if bind else None,
    )


def get_session_user(request: Request) -> GalleryUser | None:
    return user_from_session(request.session.get(SESSION_USER_KEY))


def _home_url() -> str:
    return f"{PUBLIC_PREFIX}/" if PUBLIC_PREFIX else "/"


@router.get("/auth/login")
async def auth_login(request: Request):
    if not oauth_configured():
        raise HTTPException(
            503,
            "Discord OAuth 未配置：请设置 DISCORD_OAUTH_CLIENT_ID / SECRET / REDIRECT_URI",
        )
    state = secrets.token_urlsafe(24)
    request.session[OAUTH_STATE_KEY] = state
    next_url = request.query_params.get("next") or _home_url()
    request.session["oauth_next"] = next_url
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "response_type": "code",
        "scope": "identify",
        "redirect_uri": DISCORD_REDIRECT_URI,
        "state": state,
    }
    return RedirectResponse(f"{DISCORD_AUTHORIZE}?{urlencode(params)}", status_code=302)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    if not oauth_configured():
        raise HTTPException(503, "OAuth 未配置")
    err = request.query_params.get("error")
    if err:
        raise HTTPException(400, f"OAuth error: {err}")

    state = request.query_params.get("state")
    code = request.query_params.get("code")
    expect = request.session.pop(OAUTH_STATE_KEY, None)
    if not state or not code or state != expect:
        raise HTTPException(400, "invalid oauth state")

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            DISCORD_TOKEN,
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, f"token exchange failed: {token_resp.text[:200]}")
        access = token_resp.json().get("access_token")
        if not access:
            raise HTTPException(400, "no access_token")

        me_resp = await client.get(
            DISCORD_ME,
            headers={"Authorization": f"Bearer {access}"},
        )
        if me_resp.status_code != 200:
            raise HTTPException(400, "failed to fetch discord user")
        me = me_resp.json()

    discord_id = str(me.get("id") or "")
    if not discord_id:
        raise HTTPException(400, "discord user missing id")

    request.session[SESSION_USER_KEY] = {
        "id": discord_id,
        "username": me.get("username") or "",
        "global_name": me.get("global_name"),
        "avatar": me.get("avatar"),
    }
    next_url = request.session.pop("oauth_next", None) or _home_url()
    return RedirectResponse(next_url, status_code=302)


@router.get("/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    return RedirectResponse(_home_url(), status_code=302)


@router.get("/api/me")
async def api_me(request: Request):
    user = get_session_user(request)
    return {
        "oauth_configured": oauth_configured(),
        "user": user.to_public() if user else None,
    }
