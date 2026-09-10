#!/usr/bin/env python3
"""Patch GenshinUID: guild channels in DISCORD_NO_MENTION_CHANNELS need no @.

Other guild channels: drop message unless the bot was mentioned / replied-to.
In whitelist channels: ignore messages that @ another bot (not us), so e.g.
@纳西妲 … does not trigger 守岸人.
Does NOT change user_type to direct (group_id stays channel id).

Run on VPS:
  cd ~/discord_bot
  .venv/bin/python patches/apply_discord_no_mention_channel_patch.py
  # then set DISCORD_NO_MENTION_CHANNELS + message_content:true, restart discordbot
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PATCH_MARKER = "# [gscore] discord no-mention channel whitelist"
PATCH_MARKER_V2 = "# [gscore] discord no-mention channel whitelist v2"
PATCH_MARKER_V3 = "# [gscore] discord no-mention channel whitelist v3"

# Insert immediately before the existing "如果有at提及，增加AT" block.
ANCHOR = """    # 如果有at提及，增加AT
    if ev.is_tome():
        message.append(Message("at", self_id))"""

INSERT = f'''{PATCH_MARKER_V3}
    if bot.adapter.get_name() == "Discord":
        import os

        from nonebot.adapters.discord import GuildMessageCreateEvent

        if isinstance(ev, GuildMessageCreateEvent):
            # Ignore other bots (incl. self) once Message Content Intent is on.
            _author = getattr(ev, "author", None)
            if _author is not None and getattr(_author, "bot", False):
                return
            # @别的机器人（且未 @ 自己）时放过，避免免 @ 频道抢答纳西妲等
            if not ev.is_tome():
                _mentions = getattr(ev, "mentions", None) or []
                _other_bots = [
                    u
                    for u in _mentions
                    if getattr(u, "bot", False) and str(getattr(u, "id", "")) != str(self_id)
                ]
                if _other_bots:
                    return
            _raw = os.environ.get("DISCORD_NO_MENTION_CHANNELS", "") or ""
            if not _raw:
                _cfg = getattr(driver.config, "discord_no_mention_channels", None)
                if _cfg is not None:
                    _raw = str(_cfg)
            _whitelist = {{x.strip() for x in str(_raw).replace(";", ",").split(",") if x.strip()}}
            _ch = str(int(ev.channel_id))
            if not ev.is_tome() and _ch not in _whitelist:
                return
            if not ev.is_tome() and _ch in _whitelist:
                message.append(Message("at", self_id))

{ANCHOR}'''


def find_init_py() -> Path:
    spec = importlib.util.find_spec("GenshinUID")
    if spec is None or not spec.origin:
        raise SystemExit(
            "GenshinUID not found. Run inside discord_bot venv:\n"
            "  .venv/bin/python patches/apply_discord_no_mention_channel_patch.py"
        )
    path = Path(spec.origin).resolve()
    if path.name != "__init__.py":
        path = path.parent / "__init__.py"
    if not path.is_file():
        raise SystemExit(f"GenshinUID __init__.py not found at {path}")
    return path


def _strip_existing_patch(text: str) -> str:
    """Remove v1/v2/v3 no-mention blocks so we can re-apply cleanly."""
    for marker in (PATCH_MARKER_V3, PATCH_MARKER_V2, PATCH_MARKER):
        while marker in text:
            start = text.index(marker)
            end = text.find(ANCHOR, start)
            if end < 0:
                raise SystemExit(f"Found {marker} but missing ANCHOR after it")
            text = text[:start] + text[end:]
    return text


def main() -> None:
    path = find_init_py()
    text = path.read_text(encoding="utf-8")

    if PATCH_MARKER_V3 in text and "_other_bots" in text:
        print(f"Already patched (v3): {path}")
        return

    text = _strip_existing_patch(text)

    if ANCHOR not in text:
        raise SystemExit(
            f"Expected at-mention block not found in {path}.\n"
            "nonebot-plugin-genshinuid version may differ — apply patch manually."
        )

    path.write_text(text.replace(ANCHOR, INSERT, 1), encoding="utf-8")
    print(f"Patched (v3): {path}")
    print("Next: set DISCORD_NO_MENTION_CHANNELS + message_content:true, restart discordbot")


if __name__ == "__main__":
    main()
    sys.exit(0)
