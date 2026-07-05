#!/usr/bin/env python3
"""Patch GenshinUID Discord attachment handling (Snowflake encode fix).

Run on VPS after pip install / upgrade:
  cd ~/discord_bot
  .venv/bin/python3 patches/apply_snowflake_patch.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

OLD_BLOCK = """            message.extend(
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

NEW_BLOCK = """            for dc_attachment in ev.attachments:
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

ALREADY_PATCHED_MARKER = 'att_data["id"] = int(att_data["id"])'


def find_init_py() -> Path:
    spec = importlib.util.find_spec("GenshinUID")
    if spec is None or not spec.origin:
        raise SystemExit(
            "GenshinUID not found. Run:\n"
            "  .venv/bin/python3 patches/apply_snowflake_patch.py"
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

    if ALREADY_PATCHED_MARKER in text:
        print(f"Already patched: {path}")
        return

    if OLD_BLOCK not in text:
        raise SystemExit(
            f"Expected block not found in {path}.\n"
            "nonebot-plugin-genshinuid version may differ — apply patch manually."
        )

    path.write_text(text.replace(OLD_BLOCK, NEW_BLOCK, 1), encoding="utf-8")
    print(f"Patched: {path}")


if __name__ == "__main__":
    main()
    sys.exit(0)
