"""投稿 pending 存盘与通过/驳回。"""

from __future__ import annotations

import io
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from PIL import Image

from . import catalog
from .config import DAILY_SUBMIT_LIMIT, PENDING_DIR, PUBLISHED_DIR

REJECT_TAGS = [
    "角色辨识度不够",
    "R18+",
    "图片分辨率太小",
    "图片太模糊",
    "缺乏美感",
    "已存在类似图片",
    "打不开原图",
    "无法竖屏裁剪",
]

# 无外链时的固定来源文案（简体）
SOURCE_STORY = "剧情截图"
SOURCE_STORY_ALIASES = frozenset({SOURCE_STORY})
ORIG_UPLOAD_MAX_BYTES = 20 * 1024 * 1024
_ORIG_NAME = "orig"  # pending 目录内投稿原图：orig.jpg / orig.png / …

_META = "meta.json"
_TZ_UTC9 = ZoneInfo("Asia/Tokyo")

STD_LUMINANCE_QUANT_TBL = [
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
]


def estimate_jpeg_quality(im: Image.Image) -> int | None:
    """根据 JPEG 亮度量化表与 IJG 标准基表逆算估计压缩质量 (Quality 1-100)。"""
    if not hasattr(im, "quantization") or not im.quantization or 0 not in im.quantization:
        return None
    qtable = list(im.quantization[0])
    if len(qtable) != 64:
        return None
    total = sum((qtable[i] * 100.0) / STD_LUMINANCE_QUANT_TBL[i] for i in range(64))
    scale = total / 64.0
    if scale <= 100:
        quality = (200.0 - scale) / 2.0
    else:
        quality = 5000.0 / scale
    return round(quality)


def validate_pile_image(data: bytes, filename: str | None = None) -> tuple[int, int, int]:
    """
    严格校验审核上传的立绘图片（按裁图步骤顺序）：
    1. 宽高比必须为 9:16（允许细微裁剪误差）
    2. 宽度必须在区间 [360, 720] 内
    3. 扩展名必须严格为 .jpg，二进制必须为有效 JPEG
    4. 导出质量统一为 80%（容差 [78, 82]）
    """
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError("文件不是有效的 JPG 图像")

    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:
        raise ValueError(f"无法解析图片内容: {e}")

    if im.format != "JPEG":
        raise ValueError(f"图片格式必须是 JPG（当前为 {im.format}）")

    w, h = im.size

    # 步骤一：宽高比 9:16（允许细微裁剪误差）
    ratio = h / w
    ideal_ratio = 16.0 / 9.0
    rel_error = abs(ratio - ideal_ratio) / ideal_ratio
    ideal_h = round(w * 16.0 / 9.0)
    if rel_error > 0.025 and abs(h - ideal_h) > 5:
        raise ValueError(
            f"图片宽高比必须为 9:16（当前尺寸 {w}×{h}，不符合 9:16 宽高比要求）"
        )

    # 步骤二：宽度区间 [360, 720]
    if not (360 <= w <= 720):
        raise ValueError(f"图片宽度必须在 [360, 720] 区间内（当前检测为 {w}px）")

    # 步骤二：扩展名必须是 .jpg
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext != "jpg":
            raise ValueError(f"文件扩展名必须是 .jpg（当前为 .{ext}）")

    # 步骤二：导出质量 80%
    q = estimate_jpeg_quality(im)
    if q is None:
        raise ValueError("未能读取到 JPEG 量化表，无法检测导出质量")
    if not (78 <= q <= 82):
        raise ValueError(f"导出质量必须为 80%（当前检测约为 {q}%，请在导出时将质量设为 80% 默认值）")

    return w, h, q


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _utc9_day_range_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    """当前 UTC+9 自然日的 [start, end) 对应 UTC 时刻。"""
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(_TZ_UTC9)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def count_submissions_today(submitter_id: str) -> int:
    """统计该用户在本 UTC+9 自然日内已创建的投稿数（含待审/通过/驳回）。"""
    if not submitter_id or not PENDING_DIR.is_dir():
        return 0
    start, end = _utc9_day_range_utc()
    n = 0
    for child in PENDING_DIR.iterdir():
        if not child.is_dir():
            continue
        meta = _read_meta(child)
        if not meta or meta.get("submitter_id") != submitter_id:
            continue
        created = _parse_iso_dt(meta.get("created_at"))
        if created is None:
            continue
        if start <= created < end:
            n += 1
    return n


def ensure_daily_quota(submitter_id: str, need: int) -> int:
    """批量投稿前检查今日剩余额度；返回剩余可投张数。"""
    used = count_submissions_today(submitter_id)
    remaining = max(0, DAILY_SUBMIT_LIMIT - used)
    if need <= 0:
        raise ValueError("请至少提交 1 条")
    if remaining <= 0:
        raise ValueError(f"今日投稿已达上限（{DAILY_SUBMIT_LIMIT} 张），请明天再试")
    if need > remaining:
        raise ValueError(
            f"本次提交 {need} 张，今日还可投 {remaining} 张（上限 {DAILY_SUBMIT_LIMIT}/日）"
        )
    return remaining


def parse_orig_url_lines(*chunks: str | None) -> list[str]:
    """从多段文本解析链接：按行拆分，去空，保序去重。"""
    out: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        if not chunk:
            continue
        for line in str(chunk).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
    return out


def is_http_orig_url(value: str | None) -> bool:
    raw = (value or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def normalize_source_label(raw: str) -> str | None:
    text = (raw or "").strip()
    if text in SOURCE_STORY_ALIASES:
        return SOURCE_STORY
    return None


def validate_orig_url(url: str) -> str:
    """校验外链原图；仅接受 http(s)。"""
    raw = (url or "").strip()
    if not raw:
        raise ValueError("请填写原图链接")
    label = normalize_source_label(raw)
    if label:
        raise ValueError("剧情截图请改用「上传原图」方式提交")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("链接须为 http(s) 地址；剧情截图请改用上传原图")
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    if "pximg.net" in host:
        raise ValueError(
            "请勿使用 Pixiv CDN 直链（i.pximg.net 会 403）。请改用作品页：https://www.pixiv.net/artworks/数字"
        )
    if "pixiv.net" in host and "/artworks/" not in parsed.path:
        raise ValueError("Pixiv 请使用作品页链接，例如 https://www.pixiv.net/artworks/12345678")
    return raw


def _guess_image_ext(filename: str | None, data: bytes) -> str:
    name = (filename or "").lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if name.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("仅支持 JPG / PNG / WebP 原图")


def validate_orig_upload(data: bytes, filename: str | None = None) -> tuple[str, int, int]:
    """校验投稿上传的原图；返回 (扩展名, w, h)。"""
    if not data:
        raise ValueError("请上传剧情截图原图")
    if len(data) > ORIG_UPLOAD_MAX_BYTES:
        raise ValueError(
            f"原图过大（上限 {ORIG_UPLOAD_MAX_BYTES // (1024 * 1024)}MB；请改用 JPG，或缩小后重试）"
        )
    ext = _guess_image_ext(filename, data)
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:
        raise ValueError(f"无法解析原图（仅支持 JPG / PNG / WebP）：{e}") from e
    w, h = im.size
    if w < 200 or h < 200:
        raise ValueError(f"原图太小（当前 {w}×{h}），请上传更高清截图")
    return ext, w, h


def find_pending_orig(sub_dir: Path) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = sub_dir / f"{_ORIG_NAME}{ext}"
        if path.is_file():
            return path
    return None


def pending_orig_path(sub_id: str) -> Path | None:
    if not re.fullmatch(r"[a-f0-9]{16}", sub_id or ""):
        return None
    return find_pending_orig(_sub_dir(sub_id))


def _sub_dir(sub_id: str) -> Path:
    return PENDING_DIR / sub_id


def _read_meta(path: Path) -> dict[str, Any] | None:
    meta = path / _META
    if not meta.is_file():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_meta(path: Path, data: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / _META).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_submission(
    *,
    char_id: str,
    orig_url: str,
    submitter_id: str,
    submitter_name: str,
    submitter_username: str,
    orig_bytes: bytes | None = None,
    orig_filename: str | None = None,
) -> dict[str, Any]:
    char = catalog.find_char(char_id)
    if not char:
        raise ValueError("角色不存在")
    used = count_submissions_today(submitter_id)
    if used >= DAILY_SUBMIT_LIMIT:
        raise ValueError(f"今日投稿已达上限（{DAILY_SUBMIT_LIMIT} 张），请明天再试")

    has_file = bool(orig_bytes)
    if has_file:
        # 剧情截图：必须带原图文件；来源文案固定为「剧情截图」
        label = normalize_source_label(orig_url) or SOURCE_STORY
        if label != SOURCE_STORY:
            raise ValueError("上传原图仅用于剧情截图来源")
        ext, orig_w, orig_h = validate_orig_upload(orig_bytes or b"", orig_filename)
        source_kind = "story"
        source_value = SOURCE_STORY
    else:
        source_value = validate_orig_url(orig_url)
        source_kind = "url"
        ext = ""
        orig_w = orig_h = 0

    sub_id = secrets.token_hex(8)
    sub_path = _sub_dir(sub_id)
    data = {
        "id": sub_id,
        "char_id": char.char_id,
        "char_name": char.name,
        "dirname": char.dirname,
        "orig_url": source_value,
        "source_kind": source_kind,
        "has_orig_file": has_file,
        "submitter_id": submitter_id,
        "submitter_name": submitter_name,
        "submitter_username": submitter_username,
        "status": "pending",
        "created_at": _utcnow(),
        "reviewed_at": None,
        "reviewer_id": None,
        "reviewer_name": None,
        "reject_tags": [],
        "reject_note": "",
        "image_id": None,
        "notify_error": None,
    }
    if has_file:
        data["orig_width"] = orig_w
        data["orig_height"] = orig_h
        data["orig_ext"] = ext.lstrip(".")
    _write_meta(sub_path, data)
    if has_file:
        (sub_path / f"{_ORIG_NAME}{ext}").write_bytes(orig_bytes or b"")
    return data


def list_submissions(
    *,
    status: str | None = None,
    submitter_id: str | None = None,
) -> list[dict[str, Any]]:
    if not PENDING_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in PENDING_DIR.iterdir():
        if not child.is_dir():
            continue
        meta = _read_meta(child)
        if not meta:
            continue
        if status and meta.get("status") != status:
            continue
        if submitter_id and meta.get("submitter_id") != submitter_id:
            continue
        out.append(meta)
    out.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    return out


def list_reviewed_submissions(
    *,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[dict[str, Any]], int]:
    """已通过 / 已驳回（含各管理员与主人），按审核时间新→旧；返回 (本页, 总数)。"""
    if not PENDING_DIR.is_dir():
        return [], 0
    out: list[dict[str, Any]] = []
    for child in PENDING_DIR.iterdir():
        if not child.is_dir():
            continue
        meta = _read_meta(child)
        if not meta:
            continue
        if meta.get("status") not in ("approved", "rejected"):
            continue
        out.append(meta)
    out.sort(
        key=lambda m: m.get("reviewed_at") or m.get("created_at") or "",
        reverse=True,
    )
    total = len(out)
    size = max(1, min(int(page_size) or 10, 100))
    page_n = max(1, int(page) or 1)
    start = (page_n - 1) * size
    return out[start : start + size], total


def save_submission(meta: dict[str, Any]) -> None:
    sub_id = str(meta.get("id") or "")
    if not re.fullmatch(r"[a-f0-9]{16}", sub_id):
        raise ValueError("invalid id")
    _write_meta(_sub_dir(sub_id), meta)


def get_submission(sub_id: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"[a-f0-9]{16}", sub_id or ""):
        return None
    return _read_meta(_sub_dir(sub_id))


def next_image_id(char_id: str) -> str:
    images = catalog.list_images(char_id) or []
    used = {int(im.image_id) for im in images if im.image_id.isdigit()}
    # 也算上 pending 里同角色已通过但尚未… 已通过会立刻进 published
    n = 1
    while n in used or n > 9999:
        n += 1
        if n > 9999:
            raise ValueError("图号已满")
    return f"{n:04d}"


def append_orig_url_line(char_dir: Path, image_id: str, url: str) -> None:
    path = char_dir / "0000原图URL.txt"
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    # 去掉同编号旧行
    kept = []
    for line in lines:
        s = line.strip()
        if s.startswith(f"{image_id} ") or s.startswith(f"{image_id}\t"):
            continue
        kept.append(line.rstrip("\n"))
    kept.append(f"{image_id} {url}")
    path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")


def reject_submission(
    sub_id: str,
    *,
    reviewer_id: str,
    reviewer_name: str,
    tags: list[str],
    note: str,
) -> dict[str, Any]:
    meta = get_submission(sub_id)
    if not meta:
        raise ValueError("投稿不存在")
    if meta.get("status") != "pending":
        raise ValueError("该投稿已处理")
    clean_tags = [t for t in tags if t in REJECT_TAGS]
    meta.update(
        {
            "status": "rejected",
            "reviewed_at": _utcnow(),
            "reviewer_id": reviewer_id,
            "reviewer_name": reviewer_name,
            "reject_tags": clean_tags,
            "reject_note": (note or "").strip()[:500],
        }
    )
    _write_meta(_sub_dir(sub_id), meta)
    return meta


def _pile_paths_for_id(dest_dir: Path, image_id: str) -> list[Path]:
    return [
        dest_dir / f"{image_id}{ext}"
        for ext in (".jpg", ".jpeg", ".png", ".webp")
        if (dest_dir / f"{image_id}{ext}").is_file()
    ]


def approve_submission(
    sub_id: str,
    *,
    reviewer_id: str,
    reviewer_name: str,
    pile_bytes: bytes,
    filename: str | None = None,
    image_id: str | None = None,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    meta = get_submission(sub_id)
    if not meta:
        raise ValueError("投稿不存在")
    if meta.get("status") != "pending":
        raise ValueError("该投稿已处理")
    if not pile_bytes:
        raise ValueError("请上传裁剪后的本图（JPG）")

    char = catalog.find_char(str(meta["char_id"]))
    if not char:
        # 目录偶发缺失时按 dirname 重建
        dirname = str(meta.get("dirname") or meta["char_id"])
        dest_dir = PUBLISHED_DIR / dirname
        dest_dir.mkdir(parents=True, exist_ok=True)
    else:
        dest_dir = char.path

    iid = (image_id or "").strip() or next_image_id(str(meta["char_id"]))
    if not re.fullmatch(r"\d{4}", iid):
        raise ValueError("图号须为四位数字")

    existing = _pile_paths_for_id(dest_dir, iid)
    overwritten = False
    if existing:
        if not allow_overwrite:
            raise ValueError(
                f"图号 {iid} 已被占用。请留空由系统自动编号；"
                "覆盖已有图仅主人可操作"
            )
        overwritten = True
        for old in existing:
            try:
                old.unlink()
            except OSError as e:
                raise ValueError(f"无法删除旧图 {old.name}：{e}") from e

    # 严格校验图片是否符合规范：.jpg / [360, 720] / 9:16 / 80% 质量
    img_w, img_h, img_q = validate_pile_image(pile_bytes, filename)

    pile_path = dest_dir / f"{iid}.jpg"
    pile_path.write_bytes(pile_bytes)
    append_orig_url_line(dest_dir, iid, str(meta["orig_url"]))

    # 剧情截图：把投稿原图一并归档为 {图号}.orig.*
    pending_orig = find_pending_orig(_sub_dir(sub_id))
    if pending_orig and pending_orig.is_file():
        for old in dest_dir.glob(f"{iid}.orig.*"):
            try:
                old.unlink()
            except OSError:
                pass
        dest_orig = dest_dir / f"{iid}.orig{pending_orig.suffix.lower()}"
        dest_orig.write_bytes(pending_orig.read_bytes())

    submitter_label = (
        str(meta.get("submitter_name") or "").strip()
        or str(meta.get("submitter_username") or "").strip()
        or str(meta.get("submitter_id") or "").strip()
    )
    catalog.append_credit_line(dest_dir, iid, submitter_label, reviewer_name)

    meta.update(
        {
            "status": "approved",
            "reviewed_at": _utcnow(),
            "reviewer_id": reviewer_id,
            "reviewer_name": reviewer_name,
            "image_id": iid,
            "image_width": img_w,
            "image_height": img_h,
            "image_quality": img_q,
            "overwritten": overwritten,
            "reject_tags": [],
            "reject_note": "",
        }
    )
    _write_meta(_sub_dir(sub_id), meta)
    return meta
