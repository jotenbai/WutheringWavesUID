#!/usr/bin/env python3
"""Fix Discord help-page button「该交互失败」.

Discord 组件交互须在 3 秒内 ACK，且不能用 PONG。改为在 ws.ping() 之前 DEFERRED_UPDATE_MESSAGE。

Run inside discord_bot venv:
  cd ~/discord_bot && .venv/bin/python patches/apply_discord_button_patch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PATCH_MARKER = "# [gscore] discord button patch applied"

EARLY_ACK_OLD = """async def get_notice_message(bot: Bot, ev: Event):
    if gsclient is None:
        return await connect()
    try:
        await gsclient.ws.ping()"""

EARLY_ACK_NEW = """async def get_notice_message(bot: Bot, ev: Event):
    if gsclient is None:
        return await connect()
    if bot.adapter.get_name() == "Discord":
        from nonebot.adapters.discord import MessageComponentInteractionEvent
        from nonebot.adapters.discord.api import InteractionCallbackType, InteractionResponse

        if isinstance(ev, MessageComponentInteractionEvent):
            await bot.call_api(
                "create_interaction_response",
                interaction_id=ev.id,
                interaction_token=ev.token,
                response=InteractionResponse(type=InteractionCallbackType.DEFERRED_UPDATE_MESSAGE),
            )
    try:
        await gsclient.ws.ping()"""

PONG_OLD = """            await bot.call_api(
                "create_interaction_response",
                interaction_id=ev.id,
                interaction_token=ev.token,
                response=InteractionResponse(type=InteractionCallbackType.PONG),
            )"""

PONG_NEW = """            pass  # ACK 已在 ws.ping() 之前完成"""


def find_init_py() -> Path:
    for base in (Path(sys.prefix), Path.cwd()):
        for pattern in ("lib/python*/site-packages/GenshinUID/__init__.py", "Lib/site-packages/GenshinUID/__init__.py"):
            for path in base.glob(pattern):
                return path
    raise FileNotFoundError("找不到 GenshinUID/__init__.py，请在 discord_bot 的 .venv 内运行")


def main() -> None:
    path = find_init_py()
    text = path.read_text(encoding="utf-8")
    if PATCH_MARKER in text:
        print("[skip] button 补丁已存在")
        return
    if EARLY_ACK_OLD not in text:
        raise RuntimeError("get_notice_message 入口不匹配，可能版本不兼容")
    text = text.replace(EARLY_ACK_OLD, EARLY_ACK_NEW, 1)
    if PONG_OLD in text:
        text = text.replace(PONG_OLD, PONG_NEW, 1)
    else:
        print("[warn] 未找到 PONG 块，可能已改过，仅应用 early ACK")
    path.write_text(text + f"\n{PATCH_MARKER}\n", encoding="utf-8")
    print(f"[ok] {path}")


if __name__ == "__main__":
    main()
