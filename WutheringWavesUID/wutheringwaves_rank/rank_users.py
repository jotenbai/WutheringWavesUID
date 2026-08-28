from __future__ import annotations

from gsuid_core.models import Event

from ..utils.database.models import WavesBind


async def get_users_for_group_rank(ev: Event):
    """群排行候选人。

    Discord：纳入本 bot 下全部绑定用户（频道 + 私聊），避免仅私聊录入的人进不了榜。
    其它平台：仍按当前群号隔离。
    """
    bot_id = getattr(ev, "bot_id", None) or getattr(ev, "real_bot_id", None)
    if bot_id == "discord":
        users = await WavesBind.get_all_data()
        if not users:
            return []
        return [u for u in users if not getattr(u, "bot_id", None) or u.bot_id == "discord"]

    return await WavesBind.get_group_all_uid(ev.group_id) or []
