#!/usr/bin/env python3
"""Fix Snowflake serialization when forwarding Discord image attachments to gsuid_core.

Run inside discord_bot venv:
  cd ~/discord_bot && .venv/bin/python patches/apply_snowflake_patch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PATCH_MARKER = "# [gscore] snowflake patch applied"

OLD = """            message.extend(
                Message(
                    (
                        "image"
                        if (content_type := dc_attachment.content_type) is not UNSET and "image" in content_type
                        else "attachment"
                    ),
                    model_dump(dc_attachment, exclude_unset=True),
                )
                for dc_attachment in ev.attachments
            )"""

NEW = """            for dc_attachment in ev.attachments:
                att_data = model_dump(dc_attachment, exclude_unset=True)
                if "id" in att_data:
                    att_data["id"] = int(att_data["id"])
                message.append(
                    Message(
                        (
                            "image"
                            if (content_type := dc_attachment.content_type) is not UNSET and "image" in content_type
                            else "attachment"
                        ),
                        att_data,
                    )
                )"""


def find_init_py() -> Path:
    for base in (Path(sys.prefix), Path.cwd()):
        for pattern in ("lib/python*/site-packages/GenshinUID/__init__.py", "Lib/site-packages/GenshinUID/__init__.py"):
            for path in base.glob(pattern):
                return path
    raise FileNotFoundError("找不到 GenshinUID/__init__.py，请在 discord_bot 的 .venv 内运行")


def main() -> None:
    path = find_init_py()
    text = path.read_text(encoding="utf-8")
    if PATCH_MARKER in text or "att_data[\"id\"] = int(att_data[\"id\"])" in text:
        print("[skip] snowflake 补丁已存在")
        return
    if OLD not in text:
        raise RuntimeError("__init__.py 中未找到附件处理代码块，可能版本不兼容")
    path.write_text(text.replace(OLD, NEW, 1) + f"\n{PATCH_MARKER}\n", encoding="utf-8")
    print(f"[ok] {path}")


if __name__ == "__main__":
    main()
