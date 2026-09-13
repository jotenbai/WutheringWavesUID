"""只读查询 gscore WavesBind（GsData.db）。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .config import GSCORE_DB


@dataclass(frozen=True)
class BindInfo:
    user_id: str
    uid: str  # 可能含多 UID，下划线拼接
    group_id: str | None


def lookup_waves_bind(discord_user_id: str) -> BindInfo | None:
    """bot_id=discord 且 uid 非空 → 视为用过「守岸人」。"""
    db = GSCORE_DB
    if not db.is_file():
        return None
    uid_key = str(discord_user_id).strip()
    if not uid_key:
        return None
    try:
        # 只读，避免锁写库
        uri = f"file:{db.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            cur = conn.execute(
                """
                SELECT user_id, uid, group_id FROM wavesbind
                WHERE user_id = ? AND bot_id = 'discord'
                  AND uid IS NOT NULL AND uid != ''
                LIMIT 1
                """,
                (uid_key,),
            )
            row = cur.fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not row:
        return None
    return BindInfo(user_id=row[0], uid=row[1], group_id=row[2])
