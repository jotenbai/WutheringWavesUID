"""Discord 服务器 ≈ QQ 群：逻辑群 ID 与绑定归属。

注意：Discord 桥接里 Event.group_id / MessageReceive.group_id 仍是**频道 ID**
（回信用）。统计/WavesBind 必须用本模块，勿直接拿 ev.group_id 当「群」。
"""

from __future__ import annotations

from gsuid_core.models import Event

from .database.models import WavesBind


def _bot_id(ev: Event) -> str | None:
    return getattr(ev, "bot_id", None) or getattr(ev, "real_bot_id", None)


def get_waves_group_id(ev: Event) -> str | None:
    """逻辑群 ID：QQ=群号；Discord=服务器 guild_id；Discord 私聊=None。"""
    if _bot_id(ev) == "discord":
        sender = getattr(ev, "sender", None) or {}
        gid = sender.get("discord_guild_id") or sender.get("guild_id")
        if gid is None or gid == "":
            return None
        return str(gid)
    return ev.group_id or None


def is_in_waves_group(ev: Event) -> bool:
    """当前会话是否处于可计入「群*」统计的场景。"""
    return get_waves_group_id(ev) is not None


async def touch_waves_group(ev: Event) -> None:
    """若在 Discord 服务器频道，把当前 guild 记入 WavesBind.group_id（可多服并存）。"""
    group_id = get_waves_group_id(ev)
    if not group_id:
        return
    bot_id = _bot_id(ev)
    user_id = getattr(ev, "user_id", None)
    if not bot_id or not user_id:
        return
    await WavesBind.append_group_id(str(user_id), bot_id, group_id)
