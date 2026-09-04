"""abyssData.json 读写"""

import json
from pathlib import Path
import time

import aiofiles
from gsuid_core.logger import logger

from ..utils.api.model import SlashChallenge, SlashDetail, SlashDifficulty, SlashHalf, SlashRole
from ..utils.resource.RESOURCE_PATH import PLAYER_PATH

ABYSS_DATA_FILENAME = "abyssData.json"

TYPE_SLASH = "slash"
TYPE_ABYSS = "abyss"
TYPE_MATRIX = "matrix"

SUPPORTED_TYPES = {TYPE_SLASH, TYPE_ABYSS, TYPE_MATRIX}
IMPLEMENTED_TYPES = {TYPE_SLASH}

CTYPE_LABEL = {TYPE_SLASH: "海墟", TYPE_ABYSS: "深塔", TYPE_MATRIX: "矩阵"}


def ctype_label(ctype: str) -> str:
    return CTYPE_LABEL.get(ctype, "挑战")


def _abyss_path(uid) -> Path:
    return PLAYER_PATH / str(uid) / ABYSS_DATA_FILENAME


def build_slash_detail_model(
    half_char_ids: list[list[int]],
    half_scores: list[int] | None = None,
    half_buff_icons: list[str] | None = None,
    half_buff_names: list[str] | None = None,
    half_buff_qualities: list[int] | None = None,
    challenge_id: int = 12,
    challenge_name: str = "无尽湍渊",
    rank: str = "",
    season_end_time_ms: int = 0,
) -> SlashDetail:
    """构造 SlashDetail model"""
    half_scores = half_scores or [0, 0]
    half_buff_icons = half_buff_icons or ["", ""]
    half_buff_names = half_buff_names or ["", ""]
    half_buff_qualities = half_buff_qualities or [5, 5]
    if not season_end_time_ms:
        season_end_time_ms = int(time.time() + 20 * 86400) * 1000

    total = sum(int(s or 0) for s in half_scores)
    if not rank:
        rank = "B" if total < 3500 else "A" if total < 4000 else "S" if total < 4500 else "SS" if total < 5000 else "SSS"

    slash_halves: list[SlashHalf] = []
    for cids, sc, bi, bn, bq in zip(half_char_ids, half_scores, half_buff_icons, half_buff_names, half_buff_qualities):
        roles = [
            SlashRole.model_validate({"roleId": int(c), "level": 0, "chain": 0, "iconUrl": ""})
            for c in (cids or [])
            if int(c) > 0
        ]
        slash_halves.append(
            SlashHalf.model_validate(
                {
                    "buffDescription": "",
                    "buffIcon": bi or "",
                    "buffName": bn or "",
                    "buffQuality": int(bq or 4),
                    "roleList": roles,
                    "score": int(sc or 0),
                }
            )
        )

    challenge = SlashChallenge.model_validate(
        {
            "challengeId": int(challenge_id or 12),
            "challengeName": challenge_name or "无尽湍渊",
            "rank": (rank or "").lower(),
            "score": total,
            "halfList": slash_halves,
        }
    )
    difficulty = SlashDifficulty.model_validate(
        {
            "allScore": total,
            "challengeList": [challenge],
            "difficulty": 2,
            "difficultyName": "再生海域-湍渊",
            "homePageBG": "",
            "maxScore": total,
            "teamIcon": "",
        }
    )
    return SlashDetail.model_validate(
        {
            "isUnlock": True,
            "seasonEndTime": int(season_end_time_ms),
            "difficultyList": [difficulty],
        }
    )


async def save_slash_detail(uid, detail: SlashDetail) -> bool:
    data = detail.model_dump()
    data["last_update"] = int(time.time())
    return await set_challenge_data(uid, TYPE_SLASH, data)


async def load_abyss_data(uid) -> dict:
    path = _abyss_path(uid)
    if not path.exists():
        return {}
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            content = await f.read()
            if not content.strip():
                return {}
            data = json.loads(content)
            return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as e:
        logger.warning(f"[abyss-data] 损坏 (uid={uid}): {e}")
        return {}
    except Exception as e:
        logger.exception(f"[abyss-data] 读取失败 (uid={uid}): {e}")
        return {}


async def save_abyss_data(uid, data: dict) -> bool:
    path_dir = PLAYER_PATH / str(uid)
    path_dir.mkdir(parents=True, exist_ok=True)
    try:
        async with aiofiles.open(_abyss_path(uid), "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        logger.exception(f"[abyss-data] 保存失败 (uid={uid}): {e}")
        return False


async def get_challenge_data(uid, ctype: str) -> dict | None:
    if ctype not in SUPPORTED_TYPES:
        return None
    data = await load_abyss_data(uid)
    v = data.get(ctype)
    return v if isinstance(v, dict) else None


async def set_challenge_data(uid, ctype: str, challenge_data: dict) -> bool:
    if ctype not in SUPPORTED_TYPES:
        return False
    data = await load_abyss_data(uid)
    if isinstance(challenge_data, dict):
        challenge_data["last_update"] = int(time.time())
    data[ctype] = challenge_data
    return await save_abyss_data(uid, data)


async def get_slash_detail_local(uid) -> SlashDetail | None:
    """读本地 slash, 直接转 SlashDetail"""
    local = await get_challenge_data(uid, TYPE_SLASH)
    if not local:
        return None
    return SlashDetail.model_validate(local)
