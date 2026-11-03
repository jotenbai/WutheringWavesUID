#!/usr/bin/env python3
"""Extend GenshinUID → gsuid-core WebSocket reconnect window.

Upstream retries only 30 × 5s (~2.5 min). On a 2G VPS, Core auto-restart
often takes longer, so the bridge gives up while Discord stays "online".

This raises the budget to 60 × 5s (~5 min).

Run on VPS after pip install / upgrade:
  cd ~/discord_bot
  .venv/bin/python3 patches/apply_gsuid_reconnect_patch.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

OLD_BLOCK = """            for _ in range(30):
                await asyncio.sleep(5)
                try:
                    await self.async_connect()
                    await self.start()
                    break
                except:  # noqa
                    logger.debug("自动连接core服务器失败...五秒后重新连接...")"""

NEW_BLOCK = """            # patched: 60×5s (~5 min) — Core cold start on small VPS can exceed 2.5 min
            for _ in range(60):
                await asyncio.sleep(5)
                try:
                    await self.async_connect()
                    await self.start()
                    break
                except:  # noqa
                    logger.debug("自动连接core服务器失败...五秒后重新连接...")"""

ALREADY_PATCHED_MARKER = "for _ in range(60):"


def find_client_py() -> Path:
    spec = importlib.util.find_spec("GenshinUID")
    if spec is None or not spec.origin:
        raise SystemExit(
            "GenshinUID not found. Run:\n"
            "  .venv/bin/python3 patches/apply_gsuid_reconnect_patch.py"
        )
    path = Path(spec.origin).resolve().parent / "client.py"
    if not path.is_file():
        raise SystemExit(f"GenshinUID client.py not found at {path}")
    return path


def main() -> None:
    path = find_client_py()
    text = path.read_text(encoding="utf-8")

    if ALREADY_PATCHED_MARKER in text and "60×5s" in text:
        print(f"Already patched: {path}")
        return

    if OLD_BLOCK not in text:
        if "for _ in range(60):" in text:
            print(f"Already patched (range=60): {path}")
            return
        raise SystemExit(
            f"Expected reconnect block not found in {path}.\n"
            "GenshinUID version may differ — apply patch manually."
        )

    path.write_text(text.replace(OLD_BLOCK, NEW_BLOCK, 1), encoding="utf-8")
    print(f"Patched: {path}")


if __name__ == "__main__":
    main()
    sys.exit(0)
