"""Discord 服务器 ≈ QQ 群：逻辑群 ID 与绑定归属。

注意：Discord 桥接里 Event.group_id / MessageReceive.group_id 仍是**频道 ID**
（回信用）。统计 / WavesBind 必须用本模块，勿直接拿 ev.group_id 当「群」。

WavesBind.group_id 中 Discord 服务器记为 ``dg:<guild_snowflake>``，
与历史误写入的频道雪花区分；QQ 群号仍为纯数字字符串。
"""

from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from .database.models import WavesBind

DISCORD_GUILD_PREFIX = "dg:"

DISCORD_AFFILIATION_HINT = (
    "[鸣潮] 请先到服务器的 bot 频道发一条指令（例如「帮助」或「绑定xxx」），"
    "完成服务器归属后再使用私聊。\n"
    "这样你才会出现在本服的群排行 / 群持有率中。"
)


def _bot_id(ev: Event) -> str | None:
    return getattr(ev, "bot_id", None) or getattr(ev, "real_bot_id", None)


def format_discord_guild_group_id(guild_id: str | int) -> str:
    gid = str(guild_id).strip()
    if gid.startswith(DISCORD_GUILD_PREFIX):
        return gid
    return f"{DISCORD_GUILD_PREFIX}{gid}"


def get_waves_group_id(ev: Event) -> str | None:
    """逻辑群 ID：QQ=群号；Discord=dg:<guild_id>；Discord 私聊=None。"""
    if _bot_id(ev) == "discord":
        sender = getattr(ev, "sender", None) or {}
        gid = sender.get("discord_guild_id") or sender.get("guild_id")
        if gid is None or gid == "":
            return None
        return format_discord_guild_group_id(gid)
    return ev.group_id or None


def is_in_waves_group(ev: Event) -> bool:
    """当前会话是否处于可计入「群*」统计的场景。"""
    return get_waves_group_id(ev) is not None


def _bind_group_tokens(group_id: str | None) -> list[str]:
    if not group_id:
        return []
    return [i for i in group_id.split("_") if i]


async def discord_bind_has_guild(user_id: str, bot_id: str = "discord") -> bool:
    """该 Discord 用户是否已写入至少一个服务器归属（dg:…）。"""
    row = await WavesBind.select_data(user_id, bot_id)
    if not row:
        return False
    return any(t.startswith(DISCORD_GUILD_PREFIX) for t in _bind_group_tokens(row.group_id))


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


async def ensure_discord_guild_affiliation(bot: Bot, ev: Event) -> bool:
    """Discord 私聊且尚未有 dg: 服务器归属时提示先去频道；返回 False 表示应中止当前指令。

    已在服务器频道：自动 touch 写入归属并放行。
    非 Discord：直接放行。
    """
    if _bot_id(ev) != "discord":
        return True

    if is_in_waves_group(ev):
        await touch_waves_group(ev)
        return True

    # 私聊或其它无 guild 的场景
    user_type = getattr(ev, "user_type", None)
    if user_type != "direct":
        # 理论上 guild 频道应已有 discord_guild_id；若缺失则仍放行以免卡死
        return True

    if await discord_bind_has_guild(str(ev.user_id), "discord"):
        return True

    at_sender = bool(ev.group_id)
    await bot.send(DISCORD_AFFILIATION_HINT, at_sender)
    return False
