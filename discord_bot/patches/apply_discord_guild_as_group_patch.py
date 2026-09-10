#!/usr/bin/env python3
"""Patch GenshinUID Discord: put guild_id into sender for WavesBind「群」归属.

MessageReceive.group_id 仍为 channel_id（回信用）。
逻辑群（Discord 服务器）经 sender['discord_guild_id'] 传递给插件。

Run on VPS:
  cd ~/discord_bot
  .venv/bin/python patches/apply_discord_guild_as_group_patch.py
  systemctl --user restart discordbot
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PATCH_MARKER = "# [gscore] discord guild_id in sender for waves group"

OLD_GUILD = """        if isinstance(ev, GuildMessageCreateEvent):
            user_type = "group"
            msg_id = str(ev.message_id)
            group_id = str(int(ev.channel_id))
            sender = {
                "nickname": ev.author.username,
                "avatar": f"https://cdn.discordapp.com/avatars/{user_id}/{ev.author.avatar}",
            }"""

NEW_GUILD = f"""        if isinstance(ev, GuildMessageCreateEvent):
            user_type = "group"
            msg_id = str(ev.message_id)
            group_id = str(int(ev.channel_id))
            sender = {{
                "nickname": ev.author.username,
                "avatar": f"https://cdn.discordapp.com/avatars/{{user_id}}/{{ev.author.avatar}}",
                "discord_guild_id": str(int(ev.guild_id)),
            }}
            {PATCH_MARKER}"""

# Button / notice path: guild interactions get guild_id on the event
OLD_BTN = """            sender = {
                "nickname": nickname,
                "avatar": f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}",
            }
            pass  # ACK 已在 ws.ping() 之前完成"""

NEW_BTN = f"""            sender = {{
                "nickname": nickname,
                "avatar": f"https://cdn.discordapp.com/avatars/{{user_id}}/{{avatar}}",
            }}
            if user_type == "group" and getattr(ev, "guild_id", None) is not None:
                sender["discord_guild_id"] = str(int(ev.guild_id))
            {PATCH_MARKER}
            pass  # ACK 已在 ws.ping() 之前完成"""


def find_init_py() -> Path:
    spec = importlib.util.find_spec("GenshinUID")
    if spec is None or not spec.origin:
        raise SystemExit(
            "GenshinUID not found. Run inside discord_bot venv:\n"
            "  .venv/bin/python patches/apply_discord_guild_as_group_patch.py"
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

    if PATCH_MARKER in text and "discord_guild_id" in text:
        print(f"Already patched: {path}")
        return

    if OLD_GUILD not in text:
        raise SystemExit(
            f"Expected GuildMessageCreateEvent sender block not found in {path}.\n"
            "nonebot-plugin-genshinuid version may differ — apply patch manually."
        )

    text = text.replace(OLD_GUILD, NEW_GUILD, 1)

    if OLD_BTN in text:
        text = text.replace(OLD_BTN, NEW_BTN, 1)
    else:
        print("WARN: button sender block not found; guild messages still patched")

    path.write_text(text, encoding="utf-8")
    print(f"Patched: {path}")


if __name__ == "__main__":
    main()
    sys.exit(0)
