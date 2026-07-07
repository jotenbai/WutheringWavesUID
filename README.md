# WutheringWavesUID for Discord

基于 [gsuid_core](https://github.com/Genshin-bots/gsuid_core) 的鸣潮 Bot 插件，本仓库在 upstream 基础上**侧重国际服 + Discord 桥接部署**（`discord_bot/` 目录）。

私聊或 `@机器人` 发送「帮助」「练度统计」等指令，体验可参考 [nahida-examples](https://github.com/gamer-mitsuha/nahida-examples) 一类无前缀用法。

本仓库 fork 自 [echo/WutheringWavesUID](https://github.com/tyql688/WutheringWavesUID)，当前主要 upstream 为 [MoonShadow1976/WutheringWavesUID](https://github.com/MoonShadow1976/WutheringWavesUID)。

## 架构

```text
Discord
  → nonebot-adapter-discord
  → nonebot-plugin-genshinuid（WebSocket 连接器）
  → gsuid_core
  → WutheringWavesUID（本仓库插件）
```

| 组件 | 说明 |
|------|------|
| [gsuid_core](https://github.com/Genshin-bots/gsuid_core) | 核心，负责加载插件与 Web 控制台 |
| `WutheringWavesUID/` | 鸣潮业务逻辑（角色面板、练度、OCR 等） |
| `discord_bot/` | NoneBot2 桥接层，连接 Discord 与 gsuid_core |

## 前置要求

- 一台可公网访问的 Linux VPS（或本机长期在线环境）
- Python 3.12+（`discord_bot`）与 Python 3.13（`gsuid_core`，以官方文档为准）
- [uv](https://github.com/astral-sh/uv) 或 venv + pip
- Discord 开发者账号与 Bot Token

更完整的 gsuid_core 安装说明见 [Sayu 文档](https://docs.sayu-bot.com/Started/InstallCore.html)。

---

## 一、部署 gsuid_core 插件

在 gsuid_core 的 `plugins` 目录克隆本仓库：

```bash
cd ~/gsuid_core/gsuid_core/plugins
git clone https://github.com/jotenbai/WutheringWavesUID.git
```

启动 core（示例）：

```bash
cd ~/gsuid_core
python3.13 -m uv run core --host 0.0.0.0
```

在 Web 控制台（默认 `http://<你的主机>:8765/app`）中配置 **WutheringWavesUID**：

- **禁用强制前缀** → `disable_force_prefix: true`
- **允许空命令前缀** → `allow_empty_prefix: true`
- **OCRspace API Key**（国际服 `分析` / DC 卡片识别需要，见下文）

修改插件配置后需 **重启 gsuid_core**（Discord 发 `gs重启`，或重启 core 进程）。

更新插件：

```bash
cd ~/gsuid_core/gsuid_core/plugins/WutheringWavesUID
git pull
# 然后 gs重启
```

---

## 二、Discord 部署（`discord_bot/`）

VPS 推荐目录：`~/discord_bot`（**单层目录**，不要套 `discord_bot/discord_bot`）。

### 2.1 Discord Developer Portal

在 [Discord 开发者门户](https://discord.com/developers/applications) 创建应用并添加 Bot：

- **Message Content Intent 建议关闭**（私聊、@ 机器人、回复机器人消息仍可收到内容；开启后会监听频道全部消息，私域小群易误触发）
- 建议权限：View Channels、Send Messages、Read Message History、Attach Files、Embed Links
- 用 OAuth2 URL Generator 生成邀请链接

### 2.2 环境变量

```bash
cd ~/discord_bot
cp .env.example .env
# 编辑 .env，填入 Bot Token 与 gsuid_core 地址
```

`.env` 关键项示例：

```json
{
  "DRIVER": "~httpx+~websockets",
  "DISCORD_BOTS": [
    {
      "token": "你的BotToken",
      "intent": {
        "guild_messages": true,
        "direct_messages": true,
        "message_content": false
      }
    }
  ],
  "gsuid_core_host": "127.0.0.1",
  "gsuid_core_port": 8765,
  "gsuid_core_ws_token": ""
}
```

门户与 `.env` 中 `message_content` 设置须一致。

### 2.3 安装与启动

```bash
cd ~/discord_bot
python3.12 -m venv .venv
~/discord_bot/.venv/bin/pip install -U pip
~/discord_bot/.venv/bin/pip install "nonebot2[fastapi]" nb-cli nonebot-adapter-discord \
  nonebot-plugin-genshinuid nonebot-plugin-apscheduler httpx websockets

# 必需补丁（重建 .venv 或升级 genshinuid 后需重跑）
~/discord_bot/.venv/bin/python patches/apply_snowflake_patch.py
~/discord_bot/.venv/bin/python patches/apply_discord_button_patch.py
~/discord_bot/.venv/bin/python patches/apply_discord_reply_patch.py

~/discord_bot/.venv/bin/nb run
# 或：~/discord_bot/.venv/bin/python bot.py
```

若 `source .venv/bin/activate` 报错，全程用 `~/discord_bot/.venv/bin/python` / `.venv/bin/nb` 即可。

### 2.4 补丁说明

`nonebot-plugin-genshinuid` 对 Discord 有几处已知问题，补丁脚本会修改 **venv 内已安装的 GenshinUID**：

| 脚本 | 作用 | 典型现象（未打补丁时） |
|------|------|------------------------|
| [`apply_snowflake_patch.py`](discord_bot/patches/apply_snowflake_patch.py) | 修复附件 Snowflake 序列化 | `Encoding objects of type Snowflake is unsupported` |
| [`apply_discord_button_patch.py`](discord_bot/patches/apply_discord_button_patch.py) | 修复帮助页按钮 ACK | 点按钮「该交互失败」 |
| [`apply_discord_reply_patch.py`](discord_bot/patches/apply_discord_reply_patch.py) | 回复引用原指令，不 @ 用户 | 无灰色引用条；多人同时发指令难区分 |

打完补丁需 **重启 discordbot**。

### 2.5 OCR.space（国际服 Discord 卡片识别）

国际服缺少库街区，**角色面板截图识别**（如 `分析` / `ww分析`）依赖 [OCR.space](https://ocr.space/OCRAPI) API。

**配置：** gsuid_core 网页控制台 → WutheringWavesUID → `OCRspaceApiKeyList`，填入 API Key（可多个，插件轮询）。

**注意：**

- VPS 需能访问 `api.ocr.space`
- 游戏内卡片须为**中文界面**（默认 `cht`）；英文卡会提示 `Please use chinese card!`
- 可选 `CardImgCheck`：声骸图标额外校验（默认 `False`）
- 私聊或频道 @ 机器人后，发角色详情截图 + 指令

### 2.6 后台常驻（screen 示例）

```bash
screen -S gscore
cd ~/gsuid_core && python3.13 -m uv run core --host 0.0.0.0
# Ctrl+A 再 D 脱离

screen -S discordbot
cd ~/discord_bot && .venv/bin/nb run
# Ctrl+A 再 D 脱离
```

**重启 gsuid_core 后，请同时重启 discordbot**，否则 WebSocket 会断连无响应。

---

## 使用

| 场景 | 示例 |
|------|------|
| 私聊 | `帮助`、`练度统计`、`绑定<特征码>` |
| 服务器频道 | `@机器人 帮助` |
| 国际服数据 | 绑定 UID → 发送官方 DC 卡片图 `分析` → `角色面板` |

指令详情见插件内 `帮助` 图，或 [官方插件文档](https://docs.sayu-bot.com/PluginsHelp/WutheringWavesUID.html)。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 私聊/频道无回复，discordbot 有 `【发送】` 但无 `【接收】` | 确认 gscore 在监听 8765；**重启 discordbot** |
| 发图报错 Snowflake | 运行 `apply_snowflake_patch.py`，重启 discordbot |
| 按钮「该交互失败」 | 运行 `apply_discord_button_patch.py`，重启 discordbot |
| 重启 core 后 Discord 无响应 | 同时重启 discordbot |
| `pip install -U` 或重建 venv 后问题复发 | 重新运行三个补丁脚本 |
| `nb` 找不到 | 安装 `nb-cli`；或用 `python bot.py` 启动 |

---

## 致谢

本仓库业务功能建立在社区长期维护的鸣潮插件之上，特别感谢：

- **[CM-Edelweiss/WutheringWavesUID](https://github.com/CM-Edelweiss/WutheringWavesUID)** — 早期插件基础
- **[MoonShadow1976/WutheringWavesUID](https://github.com/MoonShadow1976/WutheringWavesUID)** — 当前主要 upstream 维护
- **[gsuid_core](https://github.com/Genshin-bots/gsuid_core)** 与 **[nonebot-plugin-genshinuid](https://github.com/Genshin-bots/nonebot-plugin-genshinuid)** — 核心与多平台连接器
- 以及各攻略作者、数据与 OCR 相关开源项目（详见 upstream 历史贡献）

## 许可证

[GPL-3.0 License](LICENSE)
