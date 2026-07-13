#!/usr/bin/env python3
"""Patch GenshinUID Discord send: reply-only (no @ mention).

1. client.py：向 discord_send 传入 msg.msg_id
2. send_utils.py：message_reference + 发送失败时去掉引用重试（带图指令）

Run on VPS:
  cd ~/discord_bot && .venv/bin/python patches/apply_discord_reply_patch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PATCH_MARKER = "# [gscore] discord reply-only patch (no mention)"

CLIENT_OLD = """                            elif msg.bot_id == "discord":
                                recall_id = await discord_send(
                                    bot,
                                    content,
                                    image,
                                    node,
                                    at_list,
                                    markdown,
                                    buttons,
                                    record,
                                    video,
                                    msg.target_id,
                                    msg.target_type,
                                    group_id,
                                )"""

CLIENT_NEW = """                            elif msg.bot_id == "discord":
                                recall_id = await discord_send(
                                    bot,
                                    content,
                                    image,
                                    node,
                                    at_list,
                                    markdown,
                                    buttons,
                                    record,
                                    video,
                                    msg.target_id,
                                    msg.target_type,
                                    group_id,
                                    msg.msg_id or None,
                                )"""

SIGNATURE_OLD = """    target_type: Optional[str],
    group_id: Optional[str],
) -> Optional[Union[str, List[str]]]:"""

SIGNATURE_NEW = """    target_type: Optional[str],
    group_id: Optional[str],
    msg_id: Optional[str] = None,
) -> Optional[Union[str, List[str]]]:"""

IMPORT_OLD = """    from nonebot.adapters.discord import Bot, Message, MessageSegment
    from nonebot.adapters.discord.api import ActionRow"""

IMPORT_NEW = """    from nonebot.adapters.discord import Bot, Message, MessageSegment
    from nonebot.adapters.discord.api import ActionRow, AllowedMention, MessageReference"""

AT_AND_SEND_OLD = """            if at_list and target_type == "group":
                for at in at_list:
                    message.append(MessageSegment.mention_user(int(at)))

            if markdown:
                logger.warning("[gscore] discord暂不支持发送markdown消息")
            if buttons:
                bt = []
                for button in buttons:
                    if isinstance(button, Dict):
                        bt.append(_dc_kb(button))
                        if len(bt) >= 2:
                            message.append(MessageSegment.component(ActionRow(components=bt)))
                            bt = []
                    if isinstance(button, List):
                        _t = []
                        for i in button:
                            _t.append(_dc_kb(i))
                        else:
                            message.append(MessageSegment.component(ActionRow(components=_t)))
                            _t = []

            await bot.call_api("trigger_typing_indicator", channel_id=group_id)
            ret = await bot.send_to(
                channel_id=int(group_id),
                message=message,
            )"""

AT_AND_SEND_V1 = """            allowed_mentions = None
            if target_type == "group":
                if at_list:
                    for at in reversed(at_list):
                        message.insert(0, MessageSegment.mention_user(int(at)))
                    allowed_mentions = AllowedMention(
                        parse=[],
                        users=[int(at) for at in at_list],
                        roles=[],
                        replied_user=False,
                    )
                if msg_id:
                    message.append(
                        MessageSegment.reference(MessageReference(message_id=int(msg_id)))
                    )
                    if not at_list:
                        allowed_mentions = AllowedMention(
                            parse=[],
                            users=[],
                            roles=[],
                            replied_user=True,
                        )

            if markdown:
                logger.warning("[gscore] discord暂不支持发送markdown消息")
            if buttons:
                bt = []
                for button in buttons:
                    if isinstance(button, Dict):
                        bt.append(_dc_kb(button))
                        if len(bt) >= 2:
                            message.append(MessageSegment.component(ActionRow(components=bt)))
                            bt = []
                    if isinstance(button, List):
                        _t = []
                        for i in button:
                            _t.append(_dc_kb(i))
                        else:
                            message.append(MessageSegment.component(ActionRow(components=_t)))
                            _t = []

            await bot.call_api("trigger_typing_indicator", channel_id=group_id)
            ret = await bot.send_to(
                channel_id=int(group_id),
                message=message,
                allowed_mentions=allowed_mentions,
            )"""

SEND_PLAIN_OLD = """            await bot.call_api("trigger_typing_indicator", channel_id=group_id)
            ret = await bot.send_to(
                channel_id=int(group_id),
                message=message,
                allowed_mentions=allowed_mentions,
            )"""

SEND_WITH_FALLBACK = """            # reply send fallback: 引用失败时仍发出图片/文字
            await bot.call_api("trigger_typing_indicator", channel_id=group_id)
            try:
                ret = await bot.send_to(
                    channel_id=int(group_id),
                    message=message,
                    allowed_mentions=allowed_mentions,
                )
            except Exception as _send_err:
                from nonebot.adapters.discord.exception import ActionFailed

                if isinstance(_send_err, ActionFailed) and msg_id:
                    _fallback = Message()
                    for _seg in message:
                        if _seg.type != "reference":
                            _fallback.append(_seg)
                    ret = await bot.send_to(
                        channel_id=int(group_id),
                        message=_fallback,
                    )
                else:
                    raise"""

AT_AND_SEND_FINAL = f"""            # reply-only: 引用原指令，不 @（频道/私聊均适用）
            allowed_mentions = None
            if msg_id:
                _ref = {{"message_id": int(msg_id), "fail_if_not_exists": False}}
                if group_id:
                    _ref["channel_id"] = int(group_id)
                message.append(
                    MessageSegment.reference(MessageReference(**_ref))
                )
                allowed_mentions = AllowedMention(
                    parse=[],
                    users=[],
                    roles=[],
                    replied_user=False,
                )

            if markdown:
                logger.warning("[gscore] discord暂不支持发送markdown消息")
            if buttons:
                bt = []
                for button in buttons:
                    if isinstance(button, Dict):
                        bt.append(_dc_kb(button))
                        if len(bt) >= 2:
                            message.append(MessageSegment.component(ActionRow(components=bt)))
                            bt = []
                    if isinstance(button, List):
                        _t = []
                        for i in button:
                            _t.append(_dc_kb(i))
                        else:
                            message.append(MessageSegment.component(ActionRow(components=_t)))
                            _t = []

{SEND_WITH_FALLBACK}"""


def find_genshinuid_dir() -> Path:
    for base in (Path(sys.prefix), Path.cwd()):
        for pattern in (
            "lib/python*/site-packages/GenshinUID",
            "Lib/site-packages/GenshinUID",
        ):
            for path in base.glob(pattern):
                if path.is_dir():
                    return path
    raise FileNotFoundError(
        "找不到 GenshinUID 包，请在 discord_bot 的 .venv 内运行本脚本"
    )


def replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[ok] {label}")
    return True


def patch_client(client_py: Path) -> None:
    text = client_py.read_text(encoding="utf-8")
    if "msg.msg_id or None" in text:
        print("[skip] client.py 已打过补丁")
        return
    if CLIENT_OLD not in text:
        raise RuntimeError("client.py 中未找到预期代码块，可能 GenshinUID 版本不兼容")
    client_py.write_text(text.replace(CLIENT_OLD, CLIENT_NEW, 1), encoding="utf-8")
    print("[ok] client.py")


def patch_send_utils(send_utils_py: Path) -> None:
    text = send_utils_py.read_text(encoding="utf-8")
    changed = False

    if "reply send fallback" not in text and SEND_PLAIN_OLD in text:
        text = text.replace(SEND_PLAIN_OLD, SEND_WITH_FALLBACK, 1)
        changed = True
        print("[ok] send_utils.py (send fallback 升级)")

    _old_ref = """                message.append(
                    MessageSegment.reference(MessageReference(message_id=int(msg_id)))
                )"""
    _new_ref = """                _ref = {"message_id": int(msg_id), "fail_if_not_exists": False}
                if group_id:
                    _ref["channel_id"] = int(group_id)
                message.append(
                    MessageSegment.reference(MessageReference(**_ref))
                )"""
    if _old_ref in text:
        text = text.replace(_old_ref, _new_ref, 1)
        changed = True
        print("[ok] send_utils.py (fail_if_not_exists 升级)")

    if "reply-only: 引用原指令" in text and "reply send fallback" in text:
        if PATCH_MARKER not in text:
            text = text.rstrip() + f"\n{PATCH_MARKER}\n"
            changed = True
        send_utils_py.write_text(text, encoding="utf-8")
        print("[skip] send_utils.py 已是完整 reply-only 补丁" if not changed else "[ok] send_utils.py")
        return

    if "msg_id: Optional[str] = None" not in text:
        if SIGNATURE_OLD not in text:
            raise RuntimeError("send_utils.py 签名不匹配，可能 GenshinUID 版本不兼容")
        text = text.replace(SIGNATURE_OLD, SIGNATURE_NEW, 1)
        changed = True
        print("[ok] send_utils.py (signature)")

    if "AllowedMention, MessageReference" not in text:
        if IMPORT_OLD not in text:
            raise RuntimeError("send_utils.py import 不匹配")
        text = text.replace(IMPORT_OLD, IMPORT_NEW, 1)
        changed = True
        print("[ok] send_utils.py (import)")

    send_utils_py.write_text(text, encoding="utf-8")

    if replace_once(send_utils_py, AT_AND_SEND_V1, AT_AND_SEND_FINAL, "send_utils.py (v1→reply-only)"):
        pass
    elif replace_once(send_utils_py, AT_AND_SEND_OLD, AT_AND_SEND_FINAL, "send_utils.py (discord_send)"):
        pass
    elif not changed:
        raise RuntimeError("send_utils.py 中未找到可替换的 discord_send 代码块")

    text = send_utils_py.read_text(encoding="utf-8")
    if PATCH_MARKER not in text:
        send_utils_py.write_text(text.rstrip() + f"\n{PATCH_MARKER}\n", encoding="utf-8")


def main() -> None:
    pkg = find_genshinuid_dir()
    patch_client(pkg / "client.py")
    patch_send_utils(pkg / "send_utils.py")
    print("完成。请重启 discordbot：screen -r discordbot → Ctrl+C → .venv/bin/nb run")


if __name__ == "__main__":
    main()
