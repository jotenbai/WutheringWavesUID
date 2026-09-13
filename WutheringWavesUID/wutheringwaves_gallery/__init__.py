"""图集同步指令（手动拉取 published → custom_role_pile）。"""

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.gallery_sync import sync_gallery_to_local

# pm=1：gscore masters（主人）+ superusers（控制台超级用户）；非 Discord 群管
sv_gallery_sync = SV("waves图集同步", priority=5, pm=1)


@sv_gallery_sync.on_fullmatch(("更新图集", "同步图集", "图集更新"))
async def send_gallery_sync_msg(bot: Bot, ev: Event):
    await bot.send("[鸣潮] 正在从网页图集同步到本机…")
    result = await sync_gallery_to_local()
    await bot.send(result)
