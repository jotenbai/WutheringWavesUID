#!/usr/bin/env python3
"""Patch GenshinUID Discord button interaction ACK (fix「该交互失败」).

Discord 消息组件交互必须在 3 秒内 ACK，且不能用 PONG（仅用于网关 Ping）。
改为 DEFERRED_UPDATE_MESSAGE，并在 ws.ping 之前立即应答。

Run on VPS (use venv python directly; avoid broken activate scripts):
  cd ~/discord_bot
  .venv/bin/python3 patches/apply_discord_button_patch.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

EARLY_ACK_MARKER = "DEFERRED_UPDATE_MESSAGE,\n                ),\n            )\n    try:\n        await gsclient.ws.ping()"

EARLY_ACK_OLD = """    if gsclient is None:
        return await connect()
    try:
        await gsclient.ws.ping()"""

EARLY_ACK_NEW = """    if gsclient is None:
        return await connect()
    if bot.adapter.get_name() == "Discord":
        from nonebot.adapters.discord import MessageComponentInteractionEvent
        from nonebot.adapters.discord.api import (
            InteractionCallbackType,
            InteractionResponse,
        )

        if isinstance(ev, MessageComponentInteractionEvent):
            await bot.call_api(
                "create_interaction_response",
                interaction_id=ev.id,
                interaction_token=ev.token,
                response=InteractionResponse(
                    type=InteractionCallbackType.DEFERRED_UPDATE_MESSAGE,
                ),
            )
    try:
        await gsclient.ws.ping()"""

LATE_ACK_OLD = """            sender = {
                "nickname": nickname,
                "avatar": f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}",
            }
            await bot.call_api(
                "create_interaction_response",
                interaction_id=ev.id,
                interaction_token=ev.token,
                response=InteractionResponse(type=InteractionCallbackType.PONG),
            )
        else:"""

LATE_ACK_NEW = """            sender = {
                "nickname": nickname,
                "avatar": f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}",
            }
        else:"""


def find_init_py() -> Path:
    spec = importlib.util.find_spec("GenshinUID")
    if spec is None or not spec.origin:
        raise SystemExit(
            "GenshinUID not found. Run:\n"
            "  .venv/bin/python3 patches/apply_discord_button_patch.py"
        )
    path = Path(spec.origin).resolve()
    if path.name != "__init__.py":
        path = path.parent / "__init__.py"
    if not path.is_file():
        raise SystemExit(f"GenshinUID __init__.py not found at {path}")
    return path


def main() -> None:
    path = find_init_py()
    text = path.read_text(encoding="utf-8")

    if EARLY_ACK_MARKER in text:
        print(f"Already patched: {path}")
        return

    if EARLY_ACK_OLD not in text:
        raise SystemExit(
            f"Early-ACK anchor not found in {path}.\n"
            "nonebot-plugin-genshinuid version may differ — apply patch manually."
        )

    if LATE_ACK_OLD not in text:
        raise SystemExit(
            f"Late PONG block not found in {path}.\n"
            "nonebot-plugin-genshinuid version may differ — apply patch manually."
        )

    text = text.replace(EARLY_ACK_OLD, EARLY_ACK_NEW, 1)
    text = text.replace(LATE_ACK_OLD, LATE_ACK_NEW, 1)
    path.write_text(text, encoding="utf-8")
    print(f"Patched Discord button ACK: {path}")


if __name__ == "__main__":
    main()
    sys.exit(0)
