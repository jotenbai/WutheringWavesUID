"""把仅含频道雪花的 Discord WavesBind 补上可推断的 dg:guild。

从「同时含频道 + dg:」的绑定推断 channel→guild，再回填纯频道绑定。
在 gsuid_core 环境或能读 GsData.db 处执行：

  python scripts/backfill_discord_dg.py [/path/to/GsData.db]
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path


def backfill(db_path: Path, *, dry_run: bool = False) -> tuple[int, int]:
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT id, user_id, group_id FROM wavesbind WHERE bot_id = ?",
        ("discord",),
    ).fetchall()

    chan_to_guild: dict[str, Counter[str]] = defaultdict(Counter)
    for _id, _uid, group_id in rows:
        toks = [t for t in (group_id or "").split("_") if t]
        dgs = [t for t in toks if t.startswith("dg:")]
        chs = [t for t in toks if not t.startswith("dg:")]
        for dg in dgs:
            for ch in chs:
                chan_to_guild[ch][dg] += 1

    cmap = {ch: ctr.most_common(1)[0][0] for ch, ctr in chan_to_guild.items() if ctr}

    fixed = 0
    skipped = 0
    for row_id, user_id, group_id in rows:
        g = group_id or ""
        if "dg:" in g:
            skipped += 1
            continue
        chs = [t for t in g.split("_") if t]
        dgs = {cmap[c] for c in chs if c in cmap}
        if len(dgs) != 1:
            skipped += 1
            continue
        dg = next(iter(dgs))
        toks = [t for t in g.split("_") if t]
        if dg in toks:
            skipped += 1
            continue
        toks.append(dg)
        new_g = "_".join(toks)
        print(f"user={user_id} {g!r} -> {new_g!r}")
        if not dry_run:
            con.execute(
                "UPDATE wavesbind SET group_id = ? WHERE id = ?",
                (new_g, row_id),
            )
        fixed += 1

    if not dry_run:
        con.commit()
    con.close()
    return fixed, skipped


if __name__ == "__main__":
    default = Path.home() / "gsuid_core/data/GsData.db"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    dry = "--dry-run" in sys.argv
    fixed, skipped = backfill(path, dry_run=dry)
    print(f"{'dry-run ' if dry else ''}fixed={fixed} skipped={skipped} db={path}")
