from typing import Any

from gsuid_core.bot import Bot
from gsuid_core.help.utils import register_help
from gsuid_core.models import Event
from gsuid_core.sv import SV
from PIL import Image

from ..utils.button import WavesButton
from ..wutheringwaves_config import PREFIX
from .change_help import get_change_help
from .get_help import ICON, get_help

sv_waves_help = SV("waves帮助")
sv_waves_change_help = SV("waves替换帮助")

# 国际服新手说明（本 fork 维护，帮助图后附链接）
GUIDANCE_URL = (
    "https://github.com/jotenbai/WutheringWavesUID/tree/master/discord_bot/command-guide"
)


@sv_waves_help.on_fullmatch("帮助")
async def send_help_img(bot: Bot, ev: Event):
    buttons: list[Any] = [
        WavesButton("登录", "登录"),
        WavesButton("查看特征码", "查看"),
        WavesButton("切换特征码", "切换"),
        WavesButton("体力", "mr"),
        WavesButton("刷新面板", "刷新面板"),
        WavesButton("练度统计", "练度统计"),
    ]
    await bot.send_option(await get_help(ev.user_pm), buttons)
    await bot.send(f"国际服新手说明（指令示例与配图）：\n{GUIDANCE_URL}")


@sv_waves_change_help.on_fullmatch(("替换帮助", "面板替换帮助"))
async def send_change_help_img(bot: Bot, ev: Event):
    await bot.send(await get_change_help(ev.user_pm))


register_help("WutheringWavesUID", f"{PREFIX}帮助", Image.open(ICON))
