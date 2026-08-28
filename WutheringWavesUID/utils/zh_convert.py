"""繁体 → 简体（指令匹配前统一转换）。"""

from __future__ import annotations

from gsuid_core.logger import logger

try:
    from opencc import OpenCC

    _cc = OpenCC("t2s")
    _s2t = OpenCC("s2t")
except ImportError:  # pragma: no cover
    _cc = None
    _s2t = None
    logger.warning("[鸣潮] 未安装 opencc，繁体指令将无法自动转简体")


# 角色官译 override（参考 wuthering.gg/zh-Hant/characters；与 OpenCC s2t 仅 3 处不一致）
# 丽贝卡→蕾貝卡、鉴心→鑒心（OpenCC 出 鑑心，正字作 鑒）、维里奈→維里奈（OpenCC 出 維裏奈）
_TRAD_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("丽贝卡", "蕾貝卡"),
    ("麗貝卡", "蕾貝卡"),
    ("瑞贝卡", "蕾貝卡"),
    ("瑞貝卡", "蕾貝卡"),
    ("维里奈", "維里奈"),
    ("維裏奈", "維里奈"),
    ("鉴心", "鑒心"),
    ("鑑心", "鑒心"),
)


class TradRaw(str):
    """出图 UI 原文，跳过繁体转换（如游戏昵称）。"""


def to_simplified(text: str) -> str:
    if not text or _cc is None:
        return text
    return _cc.convert(text)


def ui_text(text: str) -> str:
    """出图 UI 文案：简体 → 繁体（含少量 override）。"""
    if isinstance(text, TradRaw):
        return str(text)
    if not text or _s2t is None:
        return text
    if not any("\u4e00" <= c <= "\u9fff" for c in text):
        return text
    result = _s2t.convert(text)
    for src, dst in _TRAD_OVERRIDES:
        result = result.replace(src, dst)
    return result


def install_msg_process_t2s() -> None:
    """在 gsuid_core 指令匹配前，将用户文本统一转为简体。"""
    from gsuid_core import handler

    if getattr(handler.msg_process, "_ww_t2s_patched", False):
        return

    _orig = handler.msg_process

    async def _msg_process(msg):
        event = await _orig(msg)
        if event.raw_text:
            converted = to_simplified(event.raw_text)
            if converted != event.raw_text:
                logger.debug(f"[鸣潮] 指令繁简转换: {event.raw_text!r} -> {converted!r}")
                event.raw_text = converted
        if event.text:
            event.text = to_simplified(event.text)
        return event

    _msg_process._ww_t2s_patched = True  # type: ignore[attr-defined]
    handler.msg_process = _msg_process
    logger.info("[鸣潮] 已启用指令前繁体转简体")
