"""从鸣潮图集站拉取已通过本图 → custom_role_pile。"""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path

import httpx
from gsuid_core.logger import logger

from ..wutheringwaves_config import WutheringWavesConfig
from .resource.RESOURCE_PATH import CUSTOM_CARD_PATH

_PILE_NAME = re.compile(r"^(\d{4})\.(jpg|jpeg|png|webp)$", re.I)
_MARKER = ".gallery_synced"
_DEFAULT_BASE = "http://127.0.0.1:8787"

_lock = asyncio.Lock()


def _api_base() -> str:
    raw = (WutheringWavesConfig.get_config("GalleryApiUrl").data or "").strip()
    return (raw or _DEFAULT_BASE).rstrip("/")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_dirname(dirname: str, char_id: str) -> str | None:
    """仅允许 {id} 或 {id}-{名}，禁止路径穿越。"""
    if not dirname or "/" in dirname or "\\" in dirname or ".." in dirname:
        return None
    if dirname == char_id or dirname.startswith(f"{char_id}-"):
        return dirname
    return None


async def sync_gallery_to_local() -> str:
    """增量同步图集本图到 CUSTOM_CARD_PATH。返回给人看的摘要。"""
    if _lock.locked():
        return "[鸣潮] 图集正在同步中，请稍后再试。"

    async with _lock:
        base = _api_base()
        CUSTOM_CARD_PATH.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        skipped = 0
        removed = 0
        chars_touched = 0

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(60.0),
            ) as client:
                r = await client.get(f"{base}/api/manifest")
                r.raise_for_status()
                manifest = r.json()
                chars = manifest.get("chars") or []

                for char in chars:
                    char_id = str(char.get("char_id") or "")
                    dirname = _safe_dirname(str(char.get("dirname") or ""), char_id)
                    images = char.get("images") or []
                    if not char_id or not dirname:
                        continue
                    if not images:
                        # 权威侧无图：若本机有 sync 标记目录，清掉本图文件
                        dest = CUSTOM_CARD_PATH / dirname
                        if dest.is_dir() and (dest / _MARKER).is_file():
                            removed += _prune_piles(dest, set())
                        continue

                    dest = CUSTOM_CARD_PATH / dirname
                    dest.mkdir(parents=True, exist_ok=True)
                    (dest / _MARKER).write_text("1", encoding="utf-8")
                    chars_touched += 1
                    keep_ids: set[str] = set()

                    for im in images:
                        image_id = str(im.get("image_id") or "")
                        if not re.fullmatch(r"\d{4}", image_id):
                            continue
                        keep_ids.add(image_id)
                        ext = str(im.get("ext") or "jpg").lower().lstrip(".")
                        if ext == "jpeg":
                            ext = "jpg"
                        if ext not in ("jpg", "png", "webp"):
                            ext = "jpg"
                        want_sha = str(im.get("sha256") or "").lower()
                        local_path = dest / f"{image_id}.{ext}"

                        # 同编号其它扩展名先清掉，避免残留
                        for old in dest.glob(f"{image_id}.*"):
                            if old.name.startswith(f"{image_id}.orig"):
                                continue
                            if old.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and old != local_path:
                                try:
                                    old.unlink()
                                    removed += 1
                                except OSError:
                                    pass

                        if local_path.is_file() and want_sha and _sha256_file(local_path) == want_sha:
                            skipped += 1
                            continue

                        url = f"{base}/files/{char_id}/{image_id}?variant=pile"
                        try:
                            resp = await client.get(url)
                            resp.raise_for_status()
                            tmp = local_path.with_suffix(local_path.suffix + ".part")
                            tmp.write_bytes(resp.content)
                            if want_sha and _sha256_file(tmp) != want_sha:
                                tmp.unlink(missing_ok=True)
                                logger.warning(f"[图集sync] sha256 不符 {dirname}/{image_id}")
                                continue
                            tmp.replace(local_path)
                            downloaded += 1
                        except Exception as e:
                            logger.warning(f"[图集sync] 下载失败 {url}: {e}")

                    removed += _prune_piles(dest, keep_ids)

        except Exception as e:
            logger.exception("[图集sync] 失败")
            return f"[鸣潮] 图集同步失败：{e}"

        msg = (
            f"[鸣潮] 图集同步完成：更新 {downloaded}，跳过 {skipped}，"
            f"清理 {removed}，涉及角色目录 {chars_touched}。"
        )
        logger.info(msg)
        return msg


def _prune_piles(dest: Path, keep_ids: set[str]) -> int:
    n = 0
    for path in list(dest.iterdir()):
        if not path.is_file():
            continue
        m = _PILE_NAME.match(path.name)
        if not m:
            continue
        if m.group(1) not in keep_ids:
            try:
                path.unlink()
                n += 1
            except OSError:
                pass
    return n
