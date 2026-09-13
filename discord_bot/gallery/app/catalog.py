from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .config import (
    DEFAULT_REVIEWER,
    DEFAULT_SUBMITTER,
    OFFICIAL_PILE_DIR,
    PUBLISHED_DIR,
)

_DIR_RE = re.compile(r"^(\d+)(?:-(.+))?$")
_PILE_RE = re.compile(r"^(\d{4})\.(jpg|jpeg|png|webp)$", re.I)
_ORIG_RE = re.compile(r"^(\d{4})\.orig\.(jpg|jpeg|png|webp)$", re.I)
_SAFE_ID = re.compile(r"^\d+$")
_SAFE_IMG = re.compile(r"^\d{4}$")
_ORIG_URL_FILE = "0000原图URL.txt"
_ORIG_URL_LINE = re.compile(r"^(\d{4})\s+(\S.+)$")


@dataclass(frozen=True)
class CharFolder:
    char_id: str
    name: str
    dirname: str
    path: Path

    @property
    def label(self) -> str:
        return self.name or self.char_id


@dataclass(frozen=True)
class ImageAsset:
    char_id: str
    char_name: str
    dirname: str
    image_id: str
    pile_path: Path
    orig_path: Path | None
    orig_url: str | None = None
    submitter: str = DEFAULT_SUBMITTER
    reviewer: str = DEFAULT_REVIEWER

    @property
    def pile_ext(self) -> str:
        return self.pile_path.suffix.lstrip(".").lower()

    @property
    def has_orig(self) -> bool:
        return self.orig_path is not None and self.orig_path.is_file()

    def pile_sha256(self) -> str:
        h = hashlib.sha256()
        with self.pile_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def pile_mtime(self) -> float:
        return self.pile_path.stat().st_mtime

    def pile_size(self) -> int:
        return self.pile_path.stat().st_size


def _parse_dir(path: Path) -> CharFolder | None:
    if not path.is_dir():
        return None
    m = _DIR_RE.match(path.name)
    if not m:
        return None
    return CharFolder(
        char_id=m.group(1),
        name=(m.group(2) or "").strip(),
        dirname=path.name,
        path=path,
    )


def _all_char_folders() -> list[CharFolder]:
    if not PUBLISHED_DIR.is_dir():
        return []
    out: list[CharFolder] = []
    for child in sorted(PUBLISHED_DIR.iterdir(), key=lambda p: p.name):
        parsed = _parse_dir(child)
        if parsed:
            out.append(parsed)
    return out


def list_chars() -> list[CharFolder]:
    """One folder per char_id（优先带角色名的目录）。"""
    best: dict[str, CharFolder] = {}
    for c in _all_char_folders():
        prev = best.get(c.char_id)
        if prev is None or (c.name and not prev.name):
            best[c.char_id] = c
    return sorted(best.values(), key=lambda c: (c.char_id, c.dirname))


def find_char(char_id: str) -> CharFolder | None:
    if not _SAFE_ID.match(char_id):
        return None
    for c in list_chars():
        if c.char_id == char_id:
            return c
    return None


def _load_orig_urls(char_dir: Path) -> dict[str, str]:
    """读 0000原图URL.txt：每行 `0001 https://...`。"""
    path = char_dir / _ORIG_URL_FILE
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _ORIG_URL_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _scan_images(char: CharFolder) -> list[ImageAsset]:
    piles: dict[str, Path] = {}
    origs: dict[str, Path] = {}
    for f in char.path.iterdir():
        if not f.is_file():
            continue
        m_orig = _ORIG_RE.match(f.name)
        if m_orig:
            origs[m_orig.group(1)] = f
            continue
        m_pile = _PILE_RE.match(f.name)
        if m_pile:
            piles[m_pile.group(1)] = f
    orig_urls = _load_orig_urls(char.path)
    out: list[ImageAsset] = []
    for image_id in sorted(piles.keys()):
        out.append(
            ImageAsset(
                char_id=char.char_id,
                char_name=char.name,
                dirname=char.dirname,
                image_id=image_id,
                pile_path=piles[image_id],
                orig_path=origs.get(image_id),
                orig_url=orig_urls.get(image_id),
                submitter=DEFAULT_SUBMITTER,
                reviewer=DEFAULT_REVIEWER,
            )
        )
    return out


def list_images(char_id: str) -> list[ImageAsset] | None:
    char = find_char(char_id)
    if not char:
        return None
    return _scan_images(char)


def get_image(char_id: str, image_id: str) -> ImageAsset | None:
    if not _SAFE_IMG.match(image_id):
        return None
    images = list_images(char_id)
    if images is None:
        return None
    for img in images:
        if img.image_id == image_id:
            return img
    return None


def resolve_official_pile(char_id: str) -> Path | None:
    if not _SAFE_ID.match(char_id):
        return None
    if not OFFICIAL_PILE_DIR.is_dir():
        return None
    path = OFFICIAL_PILE_DIR / f"role_pile_{char_id}.png"
    return path if path.is_file() else None


def cover_image(char_id: str) -> ImageAsset | None:
    """优先 0001，否则该角色已有图中编号最小的一张。"""
    images = list_images(char_id)
    if not images:
        return None
    for im in images:
        if im.image_id == "0001":
            return im
    return images[0]


def resolve_file(char_id: str, image_id: str, variant: str) -> Path | None:
    img = get_image(char_id, image_id)
    if not img:
        return None
    if variant == "orig":
        if not img.has_orig:
            return None
        return img.orig_path
    if variant in ("pile", "card", ""):
        return img.pile_path
    return None


def build_manifest() -> dict:
    chars_out = []
    for char in list_chars():
        images = _scan_images(char)
        chars_out.append(
            {
                "char_id": char.char_id,
                "name": char.name,
                "dirname": char.dirname,
                "image_count": len(images),
                "images": [
                    {
                        "image_id": im.image_id,
                        "sha256": im.pile_sha256(),
                        "size": im.pile_size(),
                        "mtime": im.pile_mtime(),
                        "ext": im.pile_ext,
                        "orig_url": im.orig_url,
                        "submitter": im.submitter,
                        "reviewer": im.reviewer,
                    }
                    for im in images
                ],
            }
        )
    return {"version": 1, "chars": chars_out}
