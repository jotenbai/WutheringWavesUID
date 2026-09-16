from typing import Any

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.button import WavesButton
from ..utils.name_convert import get_event_command_text
from ..utils.waves_group import resolve_waves_group_id, touch_waves_group
from ..wutheringwaves_config import WutheringWavesConfig
from .draw_char_chain_hold_rate import get_char_chain_hold_rate_img
from .draw_char_hold_rate import get_char_hold_rate_img
from .draw_slash_appear_rate import draw_slash_use_rate
from .draw_tower_appear_rate import draw_tower_use_rate

sv_char_hold_rate = SV("waves角色持有率")
sv_char_chain_hold_rate = SV("waves角色共鸣链持有率")
sv_tower_appear_rate = SV("waves深塔出场率", priority=1)
sv_slash_appear_rate = SV("waves冥想出场率", priority=1)


# 角色持有率指令
@sv_char_hold_rate.on_regex(
    r"^(?:群|bot|总)?(?:角色)?持有率(?:列表|[45四五]|UP|up|全|all)?"
    r"(?:群|bot|总)?(?:排行|排名)?$",
    block=True,
)
async def handle_char_hold_rate(bot: Bot, ev: Event):
    command = get_event_command_text(ev)
    if "bot" in command.lower():
        botData = WutheringWavesConfig.get_config("botData").data
        if not botData:
            return await bot.send("[鸣潮] 未开启bot排行")
        img = await get_char_hold_rate_img(ev, "bot")
    elif "总" in command:
        img = await get_char_hold_rate_img(ev)
    else:
        # 未写范围时统一按群排行处理
        await touch_waves_group(ev)
        waves_gid, err = await resolve_waves_group_id(ev)
        if err:
            return await bot.send(err)
        img = await get_char_hold_rate_img(ev, waves_gid or "")
    buttons: list[Any] = [
        WavesButton("UP总持有率", "角色持有率UP总排行"),
        WavesButton("总持有率", "角色持有率总排行"),
        WavesButton("总持有率4星", "角色持有率4总排行"),
        WavesButton("总持有率5星", "角色持有率5总排行"),
        WavesButton("群持有率", "角色持有率群排行"),
        WavesButton("bot持有率", "角色持有率bot排行"),
    ]
    await bot.send_option(img, buttons)


# 角色持有率指令
@sv_char_chain_hold_rate.on_regex(
    r"^(?:群|bot|总)?(?:角色)?(?:共鸣链持有率|链持有率|链率)"
    r"(?:[45四五]|UP|up|全|all)?(?:群|bot|总)?(?:排行|排名)?$",
    block=True,
)
async def handle_char_chain_hold_rate(bot: Bot, ev: Event):
    command = get_event_command_text(ev)
    if "bot" in command.lower():
        botData = WutheringWavesConfig.get_config("botData").data
        if not botData:
            return await bot.send("[鸣潮] 未开启bot排行")
        img = await get_char_chain_hold_rate_img(ev, "bot")
    elif "总" in command:
        img = await get_char_chain_hold_rate_img(ev)
    else:
        # 未写范围时统一按群排行处理
        await touch_waves_group(ev)
        waves_gid, err = await resolve_waves_group_id(ev)
        if err:
            return await bot.send(err)
        img = await get_char_chain_hold_rate_img(ev, waves_gid or "")
    await bot.send(img)


# 深塔出场率指令
@sv_tower_appear_rate.on_command(
    (
        "深塔使用率",
        "深塔出场率",
        "深塔出场率列表",
        "出场率",
    ),
    block=True,
)
async def handle_tower_appear_rate(bot: Bot, ev: Event):
    img = await draw_tower_use_rate(ev)
    buttons: list[Any] = [
        WavesButton("深塔出场率", "深塔使用率"),
        WavesButton("左4出场率", "深塔出场率左"),
        WavesButton("右4出场率", "深塔出场率右"),
        WavesButton("中2出场率", "深塔出场率中"),
    ]
    await bot.send_option(img, buttons)


# 冥想出场率指令
@sv_slash_appear_rate.on_command(
    (
        "无尽总使用率",
        "无尽总出场率",
        "无尽总出场率列表",
        "无尽使用率",
        "无尽出场率",
        "无尽出场率列表",
        "冥海总使用率",
        "冥海总出场率",
        "冥海总出场率列表",
        "冥海使用率",
        "冥海出场率",
        "冥海出场率列表",
        "冥歌海墟总使用率",
        "冥歌海墟总出场率",
        "冥歌海墟总出场率列表",
        "冥歌海墟使用率",
        "冥歌海墟出场率",
        "冥歌海墟出场率列表",
    ),
    block=True,
)
async def handle_slash_appear_rate(bot: Bot, ev: Event):
    img = await draw_slash_use_rate(ev)
    buttons: list[Any] = [
        WavesButton("总出场率", "冥海出场率"),
        WavesButton("总使用率", "冥海总使用率"),
        WavesButton("上半出场率", "冥海出场率上半"),
        WavesButton("下半出场率", "冥海出场率下半"),
    ]
    await bot.send_option(img, buttons)
