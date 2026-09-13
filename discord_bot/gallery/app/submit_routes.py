"""投稿 / 我的投稿 / 审核 API。"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from .auth import GalleryUser, get_session_user
from .notify import format_review_message, notify_submitter
from .submissions import (
    REJECT_TAGS,
    approve_submission,
    create_submission,
    get_submission,
    list_submissions,
    next_image_id,
    reject_submission,
    save_submission,
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
    orig_url: str


class RejectBody(BaseModel):
    tags: list[str] = Field(default_factory=list)
    note: str = ""


@router.get("/reject-tags")
def reject_tags():
    return {"tags": REJECT_TAGS}


@router.post("/submit")
async def submit(request: Request, body: SubmitBody):
    user = _require_submitter(request)
    try:
        meta = create_submission(
            char_id=body.char_id.strip(),
            orig_url=body.orig_url,
            submitter_id=user.id,
            submitter_name=user.display_name,
            submitter_username=user.username,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "submission": meta}


@router.get("/me/submissions")
async def my_submissions(request: Request):
    user = _require_user(request)
    items = list_submissions(submitter_id=user.id)
    return {"submissions": items}


@router.get("/admin/pending")
async def admin_pending(request: Request):
    _require_admin(request)
    return {"submissions": list_submissions(status="pending"), "reject_tags": REJECT_TAGS}


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
