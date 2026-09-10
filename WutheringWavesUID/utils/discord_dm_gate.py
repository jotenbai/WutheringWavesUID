"""Discord 私聊归属门禁：未写入 dg: 前，私聊一律提示去频道。

在 msg_process（指令匹配前）改写事件，仅放行本模块的提示触发器。
"""

from __future__ import annotations

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from .waves_group import (
    DISCORD_AFFILIATION_HINT,
    _bot_id,
    discord_bind_has_guild,
    is_in_waves_group,
    touch_waves_group,
)

_GATE_SENTINEL = "__ww_discord_need_guild__"

sv_discord_dm_gate = SV("discord私聊归属门禁", priority=-100)


@sv_discord_dm_gate.on_fullmatch(_GATE_SENTINEL, block=True, prefix=False)
async def _send_affiliation_hint(bot: Bot, ev: Event):
    at_sender = bool(ev.group_id)
    await bot.send(DISCORD_AFFILIATION_HINT, at_sender)


async def apply_discord_dm_affiliation_gate(event: Event) -> None:
    """频道内 touch 归属；Discord 私聊未归属则改写为门禁哨兵。"""
    if _bot_id(event) != "discord":
        return

    if is_in_waves_group(event):
        await touch_waves_group(event)
        return

    if getattr(event, "user_type", None) != "direct":
        return

    if await discord_bind_has_guild(str(event.user_id), "discord"):
        return

    raw = (getattr(event, "raw_text", None) or "").strip()
    has_payload = bool(raw) or bool(getattr(event, "file", None)) or bool(
        getattr(event, "image", None) or getattr(event, "image_list", None)
    )
    if not has_payload:
        return

    event.raw_text = _GATE_SENTINEL
    if hasattr(event, "text"):
        event.text = _GATE_SENTINEL
    if getattr(event, "file", None):
        event.file = None
    if getattr(event, "file_name", None):
        event.file_name = None
    if getattr(event, "image", None):
        event.image = None
    if getattr(event, "image_list", None):
        event.image_list = None
    if getattr(event, "content", None):
        event.content = []


def install_discord_dm_affiliation_gate() -> None:
    """挂到 msg_process：须在繁简转换之后调用。"""
    from gsuid_core import handler

    if getattr(handler.msg_process, "_ww_discord_gate_patched", False):
        return

    _orig = handler.msg_process

    async def _msg_process(msg):
        event = await _orig(msg)
        try:
            await apply_discord_dm_affiliation_gate(event)
        except Exception:
            logger.exception("[鸣潮] Discord 私聊归属门禁处理失败")
        return event

    _msg_process._ww_discord_gate_patched = True  # type: ignore[attr-defined]
    if getattr(_orig, "_ww_t2s_patched", False):
        _msg_process._ww_t2s_patched = True  # type: ignore[attr-defined]
    handler.msg_process = _msg_process
    logger.info("[鸣潮] 已启用 Discord 私聊归属门禁（未归属一律提示去频道）")
