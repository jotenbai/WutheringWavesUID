"""待审积压时，按管理员名单轮换私信（每天一人，UTC+9 20:00）。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from .auth import admin_ids, master_ids
from .config import DATA_DIR, PUBLIC_PREFIX
from .notify import notify_discord_user
from .submissions import list_submissions

logger = logging.getLogger("gallery.admin_remind")

_UTC9 = timezone(timedelta(hours=9))
_DEFAULT_HOUR = 20
_STARTUP_DELAY_SEC = 15.0

STATE_PATH = DATA_DIR / ".admin_remind_state.json"


def remind_enabled() -> bool:
    raw = (os.getenv("GALLERY_ADMIN_REMIND") or "1").strip().lower()
    return raw not in ("0", "false", "off", "no")


def remind_tz():
    """默认固定 UTC+9（不依赖系统 tzdata）。若设置 IANA 名且可用则用之。"""
    name = (os.getenv("GALLERY_ADMIN_REMIND_TZ") or "").strip()
    if name and name not in ("UTC+9", "UTC+09", "+09:00"):
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(name)
        except Exception:
            logger.warning("GALLERY_ADMIN_REMIND_TZ=%s unavailable, fallback UTC+9", name)
    return _UTC9


def remind_hour() -> int:
    raw = (os.getenv("GALLERY_ADMIN_REMIND_HOUR") or "").strip()
    try:
        h = int(raw) if raw else _DEFAULT_HOUR
    except ValueError:
        h = _DEFAULT_HOUR
    return min(23, max(0, h))


def rotation_roster() -> list[str]:
    """稳定顺序：masters（排序）在前，其余 superusers（排序）在后。人数变化时轮换自然适应。"""
    masters = sorted(master_ids())
    rest = sorted(admin_ids() - set(masters))
    return masters + rest


def _load_state() -> dict:
    if not STATE_PATH.is_file():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def seconds_until_next_fire(now: datetime | None = None) -> float:
    tz = remind_tz()
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)
    hour = remind_hour()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def format_admin_pending_message(count: int, roster_size: int) -> str:
    base = f"https://core.jotenbai.moe{PUBLIC_PREFIX}" if PUBLIC_PREFIX else ""
    review = f"<{base}/review>" if base else "图集「审核」页"
    hour = remind_hour()
    if roster_size <= 1:
        turn = "今天仅提醒你一人"
    else:
        turn = f"今天轮到你（共 {roster_size} 位管理员轮换，每天一位）"
    return (
        f"【鸣潮图集】有 {count} 张图待审核\n"
        f"{turn}\n"
        f"审核页：{review}\n"
        f"（每天 {hour}:00 UTC+9 提醒；无积压则不发，也不跳过下一位）"
    )


async def maybe_remind_admins(*, force: bool = False) -> dict:
    """每天定点：待审>0 时只私信轮换中的下一位。无积压不推进轮换。"""
    if not remind_enabled() and not force:
        return {"skipped": "disabled"}

    tz = remind_tz()
    now = datetime.now(tz)
    today = now.date().isoformat()

    state = _load_state()
    if not force and state.get("last_remind_date") == today:
        return {"skipped": "already_today", "date": today}

    pending = list_submissions(status="pending")
    count = len(pending)
    if count <= 0:
        return {"skipped": "no_pending", "count": 0, "date": today}

    roster = rotation_roster()
    if not roster:
        return {"skipped": "no_admins", "count": count}

    idx = int(state.get("rotation_index") or 0) % len(roster)
    uid = roster[idx]
    content = format_admin_pending_message(count, len(roster))
    err = await notify_discord_user(uid, content)
    if err:
        # 失败不推进、不记「今日已发」，便于次日重试同一人
        state["last_error"] = {"uid": uid, "error": err, "at": now.isoformat()}
        _save_state(state)
        return {"sent": False, "error": err, "uid": uid, "count": count, "index": idx}

    state["last_remind_date"] = today
    state["last_sent_at"] = now.isoformat()
    state["last_count"] = count
    state["last_uid"] = uid
    state["rotation_index"] = (idx + 1) % len(roster)
    state.pop("last_error", None)
    _save_state(state)
    return {
        "sent": True,
        "uid": uid,
        "count": count,
        "index": idx,
        "next_index": state["rotation_index"],
        "roster_size": len(roster),
    }


async def admin_remind_loop() -> None:
    await asyncio.sleep(_STARTUP_DELAY_SEC)
    while True:
        delay = seconds_until_next_fire()
        logger.info("admin remind next fire in %.0fs (~%.1fh)", delay, delay / 3600.0)
        try:
            await asyncio.sleep(delay)
            result = await maybe_remind_admins()
            if result.get("sent"):
                logger.info(
                    "admin remind sent uid=%s count=%s next_index=%s",
                    result.get("uid"),
                    result.get("count"),
                    result.get("next_index"),
                )
            else:
                logger.info("admin remind skip %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("admin remind failed")
        await asyncio.sleep(60.0)
