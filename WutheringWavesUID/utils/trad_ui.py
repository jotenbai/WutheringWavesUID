"""出图 UI 繁体：在绘制阶段对 ImageDraw.text 文案做 s2t。"""

from __future__ import annotations

import contextvars

from PIL import ImageDraw

from .zh_convert import ui_text

_trad = contextvars.ContextVar("ww_trad_ui", default=False)
_patched = False
_orig_draw_text = None


def _ensure_patch() -> None:
    global _patched, _orig_draw_text
    if _patched:
        return
    _orig_draw_text = ImageDraw.ImageDraw.text

    def text(self, xy, text, fill=None, font=None, anchor=None, *args, **kwargs):
        if _trad.get() and isinstance(text, str):
            text = ui_text(text)
        return _orig_draw_text(self, xy, text, fill, font, anchor, *args, **kwargs)

    ImageDraw.ImageDraw.text = text  # type: ignore[method-assign]
    _patched = True


def enable_traditional_ui(enabled: bool):
    """开启繁体出图；返回 token，结束时须 disable_traditional_ui。"""
    if not enabled:
        return None
    _ensure_patch()
    return _trad.set(True)


def disable_traditional_ui(token) -> None:
    if token is not None:
        _trad.reset(token)
