from __future__ import annotations

from gsuid_core.models import Event

from ..utils.database.models import WavesBind
from ..utils.waves_group import get_waves_group_id, touch_waves_group


async def get_users_for_group_rank(ev: Event):
    """群排行候选人。

    Discord：当前**服务器**（guild）下绑定用户，与 QQ「群」对齐；私聊无逻辑群。
    其它平台：按当前群号隔离。
    """
    await touch_waves_group(ev)
    group_id = get_waves_group_id(ev)
    if not group_id:
        return []
    return await WavesBind.get_group_all_uid(group_id) or []
