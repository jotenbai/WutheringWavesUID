from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from . import catalog
from .config import PUBLIC_PREFIX

router = APIRouter(prefix="/api")


def _file_url(char_id: str, image_id: str, variant: str = "pile") -> str:
    return f"{PUBLIC_PREFIX}/files/{char_id}/{image_id}?variant={variant}"


def _official_url(char_id: str) -> str:
    return f"{PUBLIC_PREFIX}/official/{char_id}"


def _cover_url(char_id: str) -> str | None:
    cover = catalog.cover_image(char_id)
    if cover:
        return _file_url(char_id, cover.image_id, "pile")
    if catalog.resolve_official_pile(char_id):
        return _official_url(char_id)
    return None


@router.get("/health")
def health():
    return {"ok": True, "service": "gallery"}


@router.get("/manifest")
def manifest():
    """供机器人增量 sync：含每张本图 sha256 / mtime。"""
    return catalog.build_manifest()


@router.get("/chars")
def chars():
    items = []
    for c in catalog.list_chars():
        images = catalog.list_images(c.char_id) or []
        items.append(
            {
                "char_id": c.char_id,
                "name": c.name,
                "dirname": c.dirname,
                "label": c.label,
                "image_count": len(images),
                "cover_url": _cover_url(c.char_id),
                "cover_is_official": len(images) == 0
                and catalog.resolve_official_pile(c.char_id) is not None,
            }
        )
    return {"chars": items}


@router.get("/chars/{char_id}")
def char_detail(char_id: str):
    c = catalog.find_char(char_id)
    if not c:
        raise HTTPException(404, "character not found")
    images = catalog.list_images(char_id) or []
    return {
        "char_id": c.char_id,
        "name": c.name,
        "dirname": c.dirname,
        "label": c.label,
        "image_count": len(images),
    }


@router.get("/chars/{char_id}/images")
def char_images(char_id: str):
    images = catalog.list_images(char_id)
    if images is None:
        raise HTTPException(404, "character not found")
    return {
        "char_id": char_id,
        "images": [
            {
                "image_id": im.image_id,
                "ext": im.pile_ext,
                "size": im.pile_size(),
                "mtime": im.pile_mtime(),
                "orig_url": im.orig_url,
                "submitter": im.submitter,
                "reviewer": im.reviewer,
                "pile_url": _file_url(char_id, im.image_id, "pile"),
            }
            for im in images
        ],
    }


files_router = APIRouter()


@files_router.get("/official/{char_id}")
def get_official_pile(char_id: str):
    path = catalog.resolve_official_pile(char_id)
    if path is None:
        raise HTTPException(404, "official pile not found")
    return FileResponse(path, media_type="image/png")


@files_router.get("/files/{char_id}/{image_id}")
def get_file(
    char_id: str,
    image_id: str,
    variant: str = Query("pile", pattern="^(pile|orig)$"),
    download: int = Query(0, ge=0, le=1),
):
    path = catalog.resolve_file(char_id, image_id, variant)
    if path is None or not path.is_file():
        raise HTTPException(404, "file not found")
    media = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    filename = path.name
    if download:
        return FileResponse(
            path,
            media_type=media,
            filename=filename,
            content_disposition_type="attachment",
        )
    return FileResponse(path, media_type=media)
