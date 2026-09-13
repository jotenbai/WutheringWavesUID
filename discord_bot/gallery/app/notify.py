"""Discord 私信：审核结果、管理员待审提醒（可选 Bot Token）。"""

from __future__ import annotations

import os

import httpx

from .config import PUBLIC_PREFIX

BOT_TOKEN = (os.getenv("GALLERY_DISCORD_BOT_TOKEN") or "").strip()


async def notify_discord_user(discord_user_id: str, content: str) -> str | None:
    """成功返回 None；失败返回错误摘要。未配置 token 则跳过。"""
    if not BOT_TOKEN:
        return "未配置 GALLERY_DISCORD_BOT_TOKEN，跳过私信（可在「我的投稿」查看结果）"
    if not discord_user_id or not content:
        return "缺少用户或内容"
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        ch = await client.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers=headers,
            json={"recipient_id": str(discord_user_id)},
        )
        if ch.status_code not in (200, 201):
            return f"无法创建私信频道 HTTP {ch.status_code}"
        channel_id = ch.json().get("id")
        if not channel_id:
            return "私信频道无 id"
        msg = await client.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            # flags=4 → SUPPRESS_EMBEDS（双保险，与文案尖括号一致）
            json={"content": content[:1900], "flags": 4},
        )
        if msg.status_code not in (200, 201):
            return f"发送失败 HTTP {msg.status_code}"
    return None


async def notify_submitter(discord_user_id: str, content: str) -> str | None:
    return await notify_discord_user(discord_user_id, content)


def format_review_message(meta: dict) -> str:
    base = f"https://core.jotenbai.moe{PUBLIC_PREFIX}" if PUBLIC_PREFIX else ""
    # Discord：尖括号包住链接，避免自动嵌入预览图
    me_url = f"<{base}/me>" if base else "图集「我的投稿」"
    char = meta.get("char_name") or meta.get("char_id")
    status = meta.get("status")
    if status == "approved":
        iid = meta.get("image_id") or "????"
        return (
            f"【鸣潮图集】你的投稿已通过审核\n"
            f"角色：{char}\n"
            f"图号：{iid}（可用指令：{char}面板{iid}）\n"
            f"详情：{me_url}\n"
            f"（管理员在 Discord 执行「更新图集」后，机器人端方可使用该立绘出图）"
        )
    tags = meta.get("reject_tags") or []
    note = (meta.get("reject_note") or "").strip()
    tag_line = "、".join(tags) if tags else "（未选标签）"
    extra = f"\n说明：{note}" if note else ""
    return (
        f"【鸣潮图集】你的投稿未通过\n"
        f"角色：{char}\n"
        f"原因标签：{tag_line}{extra}\n"
        f"详情：{me_url}"
    )
