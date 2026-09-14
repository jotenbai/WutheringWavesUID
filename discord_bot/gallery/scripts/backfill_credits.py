"""从 pending 已通过 meta 回填 published/*/0000署名.txt。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalog import append_credit_line  # noqa: E402
from app.config import PENDING_DIR, PUBLISHED_DIR  # noqa: E402


def backfill() -> int:
    n = 0
    if not PENDING_DIR.is_dir():
        print(f"no pending dir: {PENDING_DIR}")
        return 0
    for child in sorted(PENDING_DIR.iterdir()):
        meta_path = child / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("status") != "approved":
            continue
        image_id = str(meta.get("image_id") or "").strip()
        dirname = str(meta.get("dirname") or "").strip()
        if not image_id or not dirname:
            continue
        dest = PUBLISHED_DIR / dirname
        if not dest.is_dir():
            print(f"skip missing published dir: {dirname}")
            continue
        submitter = (
            str(meta.get("submitter_name") or "").strip()
            or str(meta.get("submitter_username") or "").strip()
            or str(meta.get("submitter_id") or "").strip()
        )
        reviewer = str(meta.get("reviewer_name") or "").strip()
        append_credit_line(dest, image_id, submitter, reviewer)
        n += 1
        print(f"ok {dirname}/{image_id} submitter={submitter!r} reviewer={reviewer!r}")
    return n


if __name__ == "__main__":
    count = backfill()
    print(f"backfilled {count} credits")
