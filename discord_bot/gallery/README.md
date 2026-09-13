# 鸣潮机器人「守岸人」图集（P0：浏览 + 只读 API）

权威图库存本目录 `data/published/`。机器人侧由插件 sync 到 `custom_role_pile`（启动时 + Discord `更新图集`），出图读本地目录。

## 本地跑

```bash
cd discord_bot/gallery
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 若还没有 .env
uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
```

打开 http://127.0.0.1:8787/

## 放图验证

```text
data/published/1102-散华/
  0000原图URL.txt    # 原图直链（排在最前；每行：0001 https://...）
  0001.jpg           # 本图
```

- 目录名：`{角色id}-{中文名}`（或仅 `{id}`）；**API 只用数字 id**
- 本图：四位编号 + `.jpg` / `.png` / `.webp`
- 原图链接固定为 **`0000原图URL.txt`**（解析进 API 的 `orig_url`；详情页「原图链接」）
- **Pixiv：** 不要填 `i.pximg.net` 图片直链（会 403）；填作品页 `https://www.pixiv.net/artworks/...`
- **列表封面：** 有本图时用 **`0001.jpg`**（无 0001 则用编号最小的一张）；无本图时用官方 `role_pile_{id}.png`
- 刷新网页即可，无需重启（目录是实时扫的）

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 探活 |
| GET | `/api/chars` | 角色列表 |
| GET | `/api/chars/{id}/images` | 某角色图列表 |
| GET | `/api/manifest` | 含 sha256，供 bot sync |
| GET | `/files/{id}/{image_id}?variant=pile\|orig` | 文件；`download=1` 附件下载 |

公网经 Nginx 后前缀为 `/gallery`，例如：

- 页面：`https://core.jotenbai.moe/gallery/`
- Manifest：`https://core.jotenbai.moe/gallery/api/manifest`

VPS 上 `.env` 设 `GALLERY_PUBLIC_PREFIX=/gallery`。

## Discord 登录（P1）

1. [Discord Developer Portal](https://discord.com/developers/applications) 打开「守岸人」应用（可与 Bot 同一应用）
2. OAuth2 → Redirects 添加：`https://core.jotenbai.moe/gallery/auth/callback`
3. 复制 Client ID / Client Secret 到 VPS `~/gallery/.env`：
   - `DISCORD_OAUTH_CLIENT_ID`
   - `DISCORD_OAUTH_CLIENT_SECRET`
   - `DISCORD_OAUTH_REDIRECT_URI=https://core.jotenbai.moe/gallery/auth/callback`
4. `systemctl --user restart gallery`
5. 打开图集点「Discord 登录」；`GET /gallery/api/me` 应返回身份

管理员统一 = gscore `masters` + `superusers`（与 Discord「更新图集」完全同一拨人，全生态同权，已彻底弃用 `GALLERY_ADMIN_IDS`）。

## VPS 部署要点

1. 代码放到如 `~/gallery`（或仓内路径），venv + `pip install -r requirements.txt`
2. `.env`：`GALLERY_PUBLIC_PREFIX=/gallery`，`GALLERY_DATA_DIR` 指向数据目录
3. `deploy/gallery.service` → `~/.config/systemd/user/gallery.service`，`systemctl --user enable --now gallery`
4. 把 `deploy/nginx-gallery.snippet.conf` 并进 `core.jotenbai.moe`（**写在 `location /` 之前**），`nginx -t && reload`

管理员导出约定见仓库规则 `gallery-pile.mdc`（宽高比 9:16、宽度在区间 [360, 720]、导出质量 80%、扩展名严格为 .jpg，系统有前后端双层自动拦截）。
