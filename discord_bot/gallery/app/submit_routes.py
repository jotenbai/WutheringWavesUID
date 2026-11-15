"""投稿 / 我的投稿 / 审核 API。"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import GalleryUser, get_session_user
from .notify import format_review_message, notify_submitter
from .submissions import (
    REJECT_TAGS,
    SOURCE_STORY,
    approve_submission,
    create_submission,
    ensure_daily_quota,
    get_submission,
    list_reviewed_submissions,
    list_submissions,
    next_image_id,
    parse_orig_url_lines,
    pending_orig_path,
    reject_submission,
    save_submission,
    validate_orig_url,
)

router = APIRouter(prefix="/api", tags=["submit"])


def _require_user(request: Request) -> GalleryUser:
    user = get_session_user(request)
    if not user:
        raise HTTPException(401, "请先 Discord 登录")
    return user


def _require_submitter(request: Request) -> GalleryUser:
    user = _require_user(request)
    if not user.can_submit:
        raise HTTPException(403, "需要先在 Discord 对「守岸人」绑定 UID 后才能投稿")
    return user


def _require_admin(request: Request) -> GalleryUser:
    user = _require_user(request)
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return user


class SubmitBody(BaseModel):
    char_id: str
    orig_url: str = ""
    orig_urls: list[str] = Field(default_factory=list)


class RejectBody(BaseModel):
    tags: list[str] = Field(default_factory=list)
    note: str = ""


@router.get("/reject-tags")
def reject_tags():
    return {"tags": REJECT_TAGS}


@router.post("/submit")
async def submit(request: Request, body: SubmitBody):
    """外链投稿（Pixiv / 其它作品页）；支持多行 / 多条链接一次提交。"""
    user = _require_submitter(request)
    urls = parse_orig_url_lines(body.orig_url, *body.orig_urls)
    if not urls:
        raise HTTPException(400, "请填写原图链接（可多行，每行一条）")
    try:
        validated = [validate_orig_url(u) for u in urls]
        ensure_daily_quota(user.id, len(validated))
        created = [
            create_submission(
                char_id=body.char_id.strip(),
                orig_url=url,
                submitter_id=user.id,
                submitter_name=user.display_name,
                submitter_username=user.username,
            )
            for url in validated
        ]
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "ok": True,
        "created": len(created),
        "submission": created[0],
        "submissions": created,
    }


@router.post("/submit/upload")
async def submit_upload(
    request: Request,
    char_id: str = Form(...),
    orig: list[UploadFile] = File(...),
    source_label: str = Form(SOURCE_STORY),
):
    """剧情截图投稿：可一次多选原图，来源记为「剧情截图」。"""
    user = _require_submitter(request)
    files = [f for f in (orig or []) if f is not None]
    if not files:
        raise HTTPException(400, "请上传剧情截图原图（可一次多选）")
    try:
        ensure_daily_quota(user.id, len(files))
        created = []
        for f in files:
            raw = await f.read()
            created.append(
                create_submission(
                    char_id=char_id.strip(),
                    orig_url=source_label or SOURCE_STORY,
                    submitter_id=user.id,
                    submitter_name=user.display_name,
                    submitter_username=user.username,
                    orig_bytes=raw,
                    orig_filename=f.filename,
                )
            )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "ok": True,
        "created": len(created),
        "submission": created[0],
        "submissions": created,
    }


@router.get("/submissions/{sub_id}/orig")
async def pending_orig(request: Request, sub_id: str):
    """查看投稿上传的原图（管理员，或投稿者本人）。"""
    user = _require_user(request)
    meta = get_submission(sub_id)
    if not meta:
        raise HTTPException(404, "投稿不存在")
    if not user.is_admin and meta.get("submitter_id") != user.id:
        raise HTTPException(403, "无权查看")
    path = pending_orig_path(sub_id)
    if path is None:
        raise HTTPException(404, "该投稿没有上传原图")
    media = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, filename=path.name)


@router.get("/me/submissions")
async def my_submissions(request: Request):
    user = _require_user(request)
    items = list_submissions(submitter_id=user.id)
    return {"submissions": items}


@router.get("/admin/pending")
async def admin_pending(request: Request):
    _require_admin(request)
    return {"submissions": list_submissions(status="pending"), "reject_tags": REJECT_TAGS}


@router.get("/admin/history")
async def admin_history(
    request: Request,
    page: int = 1,
    page_size: int = 10,
):
    """全体管理员可见的审核历史（通过 + 驳回），默认每页 10 条。"""
    _require_admin(request)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    items, total = list_reviewed_submissions(page=page, page_size=page_size)
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    if page > pages:
        page = pages
        items, total = list_reviewed_submissions(page=page, page_size=page_size)
    return {
        "submissions": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.get("/admin/submissions/{sub_id}/next-image-id")
async def admin_next_id(request: Request, sub_id: str):
    _require_admin(request)
    meta = get_submission(sub_id)
    if not meta:
        raise HTTPException(404, "投稿不存在")
    try:
        return {"image_id": next_image_id(str(meta["char_id"]))}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/admin/submissions/{sub_id}/reject")
async def admin_reject(request: Request, sub_id: str, body: RejectBody):
    admin = _require_admin(request)
    try:
        meta = reject_submission(
            sub_id,
            reviewer_id=admin.id,
            reviewer_name=admin.display_name,
            tags=body.tags,
            note=body.note,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    err = await notify_submitter(str(meta["submitter_id"]), format_review_message(meta))
    if err:
        meta["notify_error"] = err
        save_submission(meta)
    return {"ok": True, "submission": meta, "notify_error": err}


@router.post("/admin/submissions/{sub_id}/approve")
async def admin_approve(
    request: Request,
    sub_id: str,
    pile: UploadFile = File(...),
    image_id: str = Form(""),
):
    admin = _require_admin(request)
    raw = await pile.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "本图过大（上限 12MB）")
    try:
        meta = approve_submission(
            sub_id,
            reviewer_id=admin.id,
            reviewer_name=admin.display_name,
            pile_bytes=raw,
            filename=pile.filename,
            image_id=image_id or None,
            allow_overwrite=bool(admin.is_master),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    err = await notify_submitter(str(meta["submitter_id"]), format_review_message(meta))
    if err:
        meta["notify_error"] = err
        save_submission(meta)
    return {"ok": True, "submission": meta, "notify_error": err}
