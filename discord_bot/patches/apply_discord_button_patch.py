#!/usr/bin/env python3
"""Patch GenshinUID Discord button interaction ACK.

Discord 蓝色按钮走 get_notice_message（on_notice）。
交互只能 ACK 一次；重复应答 → 10062 / 40060。

v4：静默 ACK 后另发普通消息「**昵称** 点击了「按钮」」，
机器人正式回复引用该消息（频道 / 私聊一致）。

Run on VPS:
  cd ~/discord_bot
  .venv/bin/python patches/apply_discord_button_patch.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

PATCH_MARKER = "# [gscore] discord button notice ack v4"
_ACK_SKIP_CODES = (10062, 40060)

ACK_BLOCK_V3 = f"""    if bot.adapter.get_name() == "Discord":
        from nonebot.adapters.discord import MessageComponentInteractionEvent
        from nonebot.adapters.discord.api import (
            InteractionCallbackType,
            InteractionResponse,
        )
        from nonebot.adapters.discord.exception import ActionFailed

        if isinstance(ev, MessageComponentInteractionEvent):
            try:
                await bot.call_api(
                    "create_interaction_response",
                    interaction_id=ev.id,
                    interaction_token=ev.token,
                    response=InteractionResponse(
                        type=InteractionCallbackType.DEFERRED_UPDATE_MESSAGE,
                    ),
                )
            except ActionFailed as _ack_err:
                if getattr(_ack_err, "code", None) not in {_ACK_SKIP_CODES}:
                    raise"""

ACK_BLOCK = f"""    _dc_btn_msg_id = ""
    if bot.adapter.get_name() == "Discord":
        from nonebot.adapters.discord import MessageComponentInteractionEvent
        from nonebot.adapters.discord.api import (
            AllowedMention,
            InteractionCallbackType,
            InteractionResponse,
            is_not_unset,
        )
        from nonebot.adapters.discord.exception import ActionFailed

        if isinstance(ev, MessageComponentInteractionEvent):
            _hint = ""
            try:
                _member = ev.member if is_not_unset(ev.member) and ev.member else None
                if _member is not None:
                    _u = _member.user if is_not_unset(_member.user) else None
                    _nick = _member.nick if is_not_unset(_member.nick) else None
                else:
                    _u = ev.user if is_not_unset(ev.user) else None
                    _nick = None
                _name = (
                    _nick
                    or (getattr(_u, "global_name", None) if _u else None)
                    or (getattr(_u, "username", None) if _u else None)
                    or "有人"
                )
                _cid = ev.data.custom_id
                _label = _cid
                if is_not_unset(ev.message) and ev.message:
                    for _row in getattr(ev.message, "components", None) or []:
                        for _c in getattr(_row, "components", None) or []:
                            if getattr(_c, "custom_id", None) == _cid:
                                _lb = getattr(_c, "label", None)
                                if isinstance(_lb, str) and _lb:
                                    _label = _lb
                for _ch in "\\\\*_~`|>":
                    _name = str(_name).replace(_ch, "\\\\" + _ch)
                _hint = f"**{{_name}}** 点击了「{{_label}}」"
            except Exception as _hint_err:
                logger.warning(f"[gscore] discord button hint 失败: {{_hint_err}}")
                _hint = ""

            try:
                await bot.call_api(
                    "create_interaction_response",
                    interaction_id=ev.id,
                    interaction_token=ev.token,
                    response=InteractionResponse(
                        type=InteractionCallbackType.DEFERRED_UPDATE_MESSAGE,
                    ),
                )
            except ActionFailed as _ack_err:
                if getattr(_ack_err, "code", None) not in {_ACK_SKIP_CODES}:
                    raise

            # 交互回复会自动引用按钮所在消息，故提示用普通消息发送
            if _hint:
                try:
                    _hint_msg = await bot.call_api(
                        "create_message",
                        channel_id=int(ev.channel_id),
                        content=_hint,
                        allowed_mentions=AllowedMention(
                            parse=[],
                            users=[],
                            roles=[],
                            replied_user=False,
                        ),
                    )
                    _dc_btn_msg_id = str(_hint_msg.id)
                except Exception as _send_err:
                    logger.warning(f"[gscore] discord button hint 发送失败: {{_send_err}}")"""

NOTICE_FUNC_HEAD = """@get_notice.handle()
async def get_notice_message(bot: Bot, ev: Event):
    if gsclient is None:
        return await connect()"""

NOTICE_FUNC_WITH_ACK = f"""@get_notice.handle()
async def get_notice_message(bot: Bot, ev: Event):
    if gsclient is None:
        return await connect()
{ACK_BLOCK}"""

LATE_PONG_OLD = """            await bot.call_api(
                "create_interaction_response",
                interaction_id=ev.id,
                interaction_token=ev.token,
                response=InteractionResponse(type=InteractionCallbackType.PONG),
            )
        else:"""

LATE_PONG_NEW = """        else:"""

MSG_ID_EMPTY = """        if isinstance(ev, MessageComponentInteractionEvent):
            user_type = "direct" if is_not_unset(ev.channel) and ev.channel.type == ChannelType.DM else "group"
            msg_id = ""  # Discord 按钮：勿用 interaction id 作 message_reference
            group_id = str(ev.channel_id)"""

MSG_ID_HINT = """        if isinstance(ev, MessageComponentInteractionEvent):
            user_type = "direct" if is_not_unset(ev.channel) and ev.channel.type == ChannelType.DM else "group"
            msg_id = _dc_btn_msg_id  # Discord 按钮：引用「xx 点击了」提示消息（无则不引用）
            group_id = str(ev.channel_id)"""

MSG_ID_PATTERNS_OLD = (
    """        if isinstance(ev, MessageComponentInteractionEvent):
            user_type = "direct" if is_not_unset(ev.channel) and ev.channel.type == ChannelType.DM else "group"
            msg_id = str(ev.id)
            group_id = str(ev.channel_id)""",
    """        if isinstance(ev, MessageComponentInteractionEvent):
            user_type = "direct" if is_not_unset(ev.channel) and ev.channel.type == ChannelType.DM else "group"
            if is_not_unset(ev.message) and is_not_unset(ev.message.id):
                msg_id = str(ev.message.id)
            else:
                msg_id = ""
            group_id = str(ev.channel_id)""",
)

OLD_EXCEPT_PATTERNS = (
    """            except ActionFailed as _ack_err:
                if getattr(_ack_err, "code", None) != 10062:
                    raise""",
    """            except ActionFailed as _ack_err:
                if getattr(_ack_err, "code", None) not in (10062, 40060):
                    raise""",
)

NEW_EXCEPT = f"""            except ActionFailed as _ack_err:
                if getattr(_ack_err, "code", None) not in {_ACK_SKIP_CODES}:
                    raise"""

STRAY_ACK_IN_GET_MESSAGE = re.compile(
    r"""
    (?P<indent>[ \t]*)if\ bot\.adapter\.get_name\(\)\ ==\ "Discord":\n
    (?P=indent)    from\ nonebot\.adapters\.discord\ import\ MessageComponentInteractionEvent\n
    (?P=indent)    from\ nonebot\.adapters\.discord\.api\ import\ \(\n
    (?P=indent)        InteractionCallbackType,\n
    (?P=indent)        InteractionResponse,\n
    (?P=indent)    \)\n
    (?P=indent)\n
    (?P=indent)    if\ isinstance\(ev,\ MessageComponentInteractionEvent\):\n
    (?P=indent)        await\ bot\.call_api\(\n
    (?P=indent)            "create_interaction_response",\n
    (?P=indent)            interaction_id=ev\.id,\n
    (?P=indent)            interaction_token=ev\.token,\n
    (?P=indent)            response=InteractionResponse\(\n
    (?P=indent)                type=InteractionCallbackType\.DEFERRED_UPDATE_MESSAGE,\n
    (?P=indent)            \),\n
    (?P=indent)        \)\n
    """,
    re.VERBOSE,
)

INTERACTION_ACK_CALL = 'await bot.call_api(\n                "create_interaction_response"'


def find_init_py() -> Path:
    spec = importlib.util.find_spec("GenshinUID")
    if spec is None or not spec.origin:
        raise SystemExit(
            "GenshinUID not found. Run:\n"
            "  .venv/bin/python patches/apply_discord_button_patch.py"
        )
    path = Path(spec.origin).resolve()
    if path.name != "__init__.py":
        path = path.parent / "__init__.py"
    if not path.is_file():
        raise SystemExit(f"GenshinUID __init__.py not found at {path}")
    return path


def keep_first_interaction_ack_in_notice(text: str) -> tuple[str, int]:
    """get_notice_message 内只保留第一处 create_interaction_response。"""
    fn_start = text.find("async def get_notice_message")
    fn_end = text.find("@get_message.handle()", fn_start)
    if fn_start == -1 or fn_end == -1:
        return text, 0

    removed = 0
    while True:
        chunk = text[fn_start:fn_end]
        first = chunk.find(INTERACTION_ACK_CALL)
        second = chunk.find(INTERACTION_ACK_CALL, first + 1)
        if second == -1:
            break
        abs_second = fn_start + second
        line_start = text.rfind("\n", fn_start, abs_second) + 1
        end = text.find("            )\n", abs_second)
        if end == -1:
            break
        end += len("            )\n")
        text = text[:line_start] + text[end:]
        fn_end = text.find("@get_message.handle()", fn_start)
        removed += 1
    return text, removed


def main() -> None:
    path = find_init_py()
    text = path.read_text(encoding="utf-8")
    changed = False

    for old in MSG_ID_PATTERNS_OLD:
        if old in text:
            text = text.replace(old, MSG_ID_EMPTY, 1)
            changed = True
            print("[ok] button msg_id → empty")
            break

    for old_ex in OLD_EXCEPT_PATTERNS:
        if old_ex in text and old_ex != NEW_EXCEPT:
            text = text.replace(old_ex, NEW_EXCEPT, 1)
            changed = True
            print("[ok] except 升级：忽略 10062 + 40060")
            break

    new_text, n = STRAY_ACK_IN_GET_MESSAGE.subn("", text, count=1)
    if n:
        text = new_text
        changed = True
        print("[ok] removed stray ACK from get_all_message")

    if LATE_PONG_OLD in text:
        text = text.replace(LATE_PONG_OLD, LATE_PONG_NEW, 1)
        changed = True
        print("[ok] removed PONG from get_notice")

    text, dup = keep_first_interaction_ack_in_notice(text)
    if dup:
        changed = True
        print(f"[ok] removed {dup} duplicate interaction ACK in get_notice")

    if ACK_BLOCK_V3 in text and ACK_BLOCK not in text:
        text = text.replace(ACK_BLOCK_V3, ACK_BLOCK, 1)
        changed = True
        print("[ok] get_notice ACK v3 → v4（点击提示消息）")

    if MSG_ID_EMPTY in text:
        text = text.replace(MSG_ID_EMPTY, MSG_ID_HINT, 1)
        changed = True
        print("[ok] button msg_id → 引用点击提示")

    if ACK_BLOCK not in text:
        if NOTICE_FUNC_HEAD not in text:
            raise SystemExit(
                f"get_notice_message anchor not found in {path}.\n"
                "nonebot-plugin-genshinuid version may differ."
            )
        text = text.replace(NOTICE_FUNC_HEAD, NOTICE_FUNC_WITH_ACK, 1)
        changed = True
        print("[ok] inserted get_notice DEFERRED ACK (v3)")

    # 刷新 marker（v2→v3 也会重跑）
    text = re.sub(
        r"# \[gscore\] discord button notice ack v\d+\n?",
        "",
        text,
    )
    text = text.rstrip() + f"\n{PATCH_MARKER}\n"
    changed = True

    path.write_text(text, encoding="utf-8")
    print(f"Patched: {path}")
    print("请重启 discordbot：systemctl --user restart discordbot")


if __name__ == "__main__":
    main()
    sys.exit(0)
