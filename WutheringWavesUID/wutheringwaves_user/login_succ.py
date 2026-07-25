from typing import Any

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.button import WavesButton
from ..utils.database.models import WavesUser
from ..utils.waves_api import waves_api
from ..wutheringwaves_config import PREFIX

login_fail_cn = "[鸣潮] 特征码[{}]已登录，但刷新面板失败，请使用【{}每日】检查是否成功登录\n"
login_fail_net = (
    "[鸣潮] 特征码[{}]已登录，但刷新面板失败。\n"
    "国际服登录成功不等于已有角色面板数据。\n"
    "请使用【{}分析】发送官方 DC 卡片图，或【{}pcap帮助】上传抓包数据后再刷新面板。\n"
)


async def login_success_msg(bot: Bot, ev: Event, waves_user: WavesUser):
    buttons: list[Any] = [
        WavesButton("体力", "mr"),
        WavesButton("刷新面板", "刷新面板"),
        WavesButton("深塔", "深塔"),
        WavesButton("冥歌海墟", "冥海"),
    ]

    from ..wutheringwaves_charinfo.draw_refresh_char_card import (
        draw_refresh_char_detail_img,
    )

    msg = await draw_refresh_char_detail_img(bot, ev, waves_user.user_id, waves_user.uid, buttons)
    if isinstance(msg, bytes):
        return await bot.send_option(msg, buttons)
    else:
        at_sender = True if ev.group_id else False
        if waves_api.is_net(waves_user.uid):
            text = login_fail_net.format(waves_user.uid, PREFIX, PREFIX)
        else:
            text = login_fail_cn.format(waves_user.uid, PREFIX)
        return await bot.send(text, at_sender)
