# 图集站（可选 · 自建运维）

> **第三方 Bot 开发者请先看仓库根 [README「开放 API」](../../README.md#开放-api第三方-bot-同步图集)。**  
> 本目录是维护者自建「投稿 + 审核」整站的参考实现，**不是**部署 Discord 机器人的必需步骤；clone 插件后也不会自动占用 `/gallery` 或 8787 端口。

生产常见落点：VPS `~/gallery/`（与 `~/discord_bot`、`~/gsuid_core` 平级），公网由 Nginx 反代到 `127.0.0.1:8787`。

## 本地 / VPS 跑（自建时）

```bash
cd discord_bot/gallery   # 或已同步到的 ~/gallery
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 填 OAuth 等；勿提交 .env
uvicorn app.main:app --host 127.0.0.1 --port 8787
```

- systemd 模板：`deploy/gallery.service`
- Nginx 片段：`deploy/nginx-gallery.snippet.conf`（须写在 `location /` **之前**）
- `.env` 公网前缀示例：`GALLERY_PUBLIC_PREFIX=/gallery`

权威本图：`data/published/{char_id}-{名}/0001.jpg` 等；待审：`data/pending/`。本图规范见仓库规则 `gallery-pile.mdc`。

管理员 = gscore `masters` + `superusers`；覆盖已有图号仅 `masters`。

待审积压提醒（可选）：配置 `GALLERY_DISCORD_BOT_TOKEN` 后，默认每天 **UTC+9 20:00** 在待审 > 0 时只私信**一位**管理员（`masters` → `superusers` 轮换）；无人积压则不发也不跳号。`GALLERY_ADMIN_REMIND=0` 关闭；小时/时区见 `.env.example`。
