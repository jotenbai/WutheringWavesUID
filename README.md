# WutheringWavesUID for Discord

本仓库在 [MoonShadow1976/WutheringWavesUID](https://github.com/MoonShadow1976/WutheringWavesUID) 基础上**侧重国际服 + Discord 桥接部署**（`discord_bot/` 目录）。

**主要目的：** 帮助玩家把握角色培养进度（面板、练度、声骸评分等）。国际服新手可先看 [指令使用说明与示例](discord_bot/command-guide/manual.md)。

私聊或 `@机器人` 发送「帮助」「练度统计」等指令，体验可参考 [nahida-examples](https://github.com/gamer-mitsuha/nahida-examples) 一类无前缀用法。

自用小服：试用机器人或联系维护者可加入 [Discord](https://discord.com/invite/eWnWyGqEXM)。Bot 已关闭 Public，不能自行邀请至其他服务器；纯属个人兴趣，仅供小范围使用。
[服务条款](discord_bot/docs/terms-of-service.md) · [隐私政策](discord_bot/docs/privacy-policy.md)

## 架构

```text
Discord
  → nonebot-adapter-discord
  → nonebot-plugin-genshinuid（WebSocket 连接器）
  → gsuid_core
  → WutheringWavesUID（本仓库插件）
```

| 组件                                                     | 说明                                                                     |
| -------------------------------------------------------- | ------------------------------------------------------------------------ |
| [gsuid_core](https://github.com/Genshin-bots/gsuid_core) | 核心，负责加载插件与 Web 控制台                                          |
| `WutheringWavesUID/`                                     | 鸣潮业务逻辑（角色面板、练度、OCR 等）                                   |
| `discord_bot/`                                           | Discord 桥接、补丁、systemd 模板与法务文档（本 fork 相对上游的额外内容） |

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

在 Web 控制台（默认 `http://<你的主机>:8765/app`，若已用域名反代则为 `https://core.你的域名/app/`）中配置 **WutheringWavesUID**：

- **禁用强制前缀** → `disable_force_prefix: true`
- **允许空命令前缀** → `allow_empty_prefix: true`
- **OCRspace API Key**（国际服 `分析` / DC 卡片识别需要，见下文）
- **鸣潮登录 url（`WavesLoginUrl`）**（可选）：填公网可访问的站点根，如 `https://core.jotenbai.moe`（不要带末尾 `/`）。留空则机器人会拼 `http://公网IP:8765`，易暴露 IP。配置后 `登录` / `上传pcap` 等链接会使用该域名。

修改插件配置后需 **重启 gsuid_core**（Discord 发 `core重启`，或 `systemctl --user restart gscore`）。

### 网页控制台小建议（可选）

路径：**管理核心** → **框架配置** → **自动更新**。

- 若已开启「自动更新 Core / 插件」，建议同时开启 **「自动重启 Core」**（默认约 4:40）。前两项只拉代码、不重启进程，不重启则更新不会真正生效。
- **「自动更新 Core/插件时将内容通知主人」** 可关闭，避免凌晨更新后向主人 Discord 私聊推送日志。

### 1.1 插件 Python 依赖（重要）

gsuid_core 启动时会尝试安装插件 `requirements.txt` 中的依赖，但在部分环境（如 Python 3.13 + 仅 `uv` 管理 core）下，**个别包可能未装进 core 的 venv**，导致部分子模块导入失败、对应指令静默无回复。

插件根目录 [`requirements.txt`](requirements.txt) 当前包含：

| 包名      | 用途                                         | 未安装时的典型现象                                  |
| --------- | -------------------------------------------- | --------------------------------------------------- |
| `opencc`  | 指令/OCR 繁体转简体（`zh_convert`、`analyzecard`） | `尤诺面板`、`练度统计` 等无触发；繁体指令无法自动转简 |
| `kuro-py` | 国际服登录与体力等 API（`kuro` 模块）        | 网页登录「登入失敗」；`体力` / `mr` 无数据或报错    |

在 VPS 上进入 **gsuid_core 的 venv** 手动安装（路径以你的部署为准）：

```bash
cd ~/gsuid_core
.venv/bin/python -m pip install -r gsuid_core/plugins/WutheringWavesUID/requirements.txt
# 或单独安装：
# .venv/bin/python -m pip install "opencc>=1.1.9" "kuro-py>=0.7.1"
```

安装后必须 **重启 gsuid_core**（Discord 发 `gs重启`）。仅重启 discordbot 不够。

验证（可选）：

```bash
cd ~/gsuid_core
.venv/bin/python -c "import opencc, kuro; print('ok')"
```

更新插件：

```bash
cd ~/gsuid_core/gsuid_core/plugins/WutheringWavesUID
git pull
# 然后 gs重启
```

---

## 二、Discord 部署（`discord_bot/`）

VPS 推荐目录：`~/discord_bot`

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

| 脚本                                                                                 | 作用                      | 典型现象（未打补丁时）                              |
| ------------------------------------------------------------------------------------ | ------------------------- | --------------------------------------------------- |
| [`apply_snowflake_patch.py`](discord_bot/patches/apply_snowflake_patch.py)           | 修复附件 Snowflake 序列化 | `Encoding objects of type Snowflake is unsupported` |
| [`apply_discord_button_patch.py`](discord_bot/patches/apply_discord_button_patch.py) | 修复帮助页按钮 ACK        | 点按钮「该交互失败」                                |
| [`apply_discord_reply_patch.py`](discord_bot/patches/apply_discord_reply_patch.py)   | 回复引用原指令，不 @ 用户 | 无灰色引用条；多人同时发指令难区分                  |

打完补丁需 **重启 discordbot**。

### 2.5 OCR.space（国际服 Discord 卡片识别）

国际服缺少库街区，**角色面板截图识别**（如 `分析` / `ww分析`）依赖 [OCR.space](https://ocr.space/OCRAPI) API。

**配置：** gsuid_core 网页控制台 → WutheringWavesUID → `OCRspaceApiKeyList`，填入 API Key（可多个，插件轮询）。

**注意：**

- VPS 需能访问 `api.ocr.space`
- 游戏内卡片须为**中文界面**（默认 `cht`）；英文卡会提示 `Please use chinese card!`
- 可选 `CardImgCheck`：声骸图标额外校验（默认 `False`）
- 私聊或频道 @ 机器人后，发角色详情截图 + 指令

### 2.6 后台常驻（systemd，推荐）

`screen` 在 VPS **内核更新重启后不会自动恢复**，长期运行请用 systemd。本仓库提供用户级 unit 模板：[`discord_bot/deploy/systemd/`](discord_bot/deploy/systemd/)。

**一次性安装（VPS 上，路径按你的用户目录调整）：**

```bash
mkdir -p ~/.config/systemd/user
cp /path/to/WutheringWavesUID/discord_bot/deploy/systemd/*.service ~/.config/systemd/user/
# 若 WorkingDirectory / ExecStart 与你的路径不同，先编辑这两个 .service

systemctl --user daemon-reload
systemctl --user enable --now gscore.service
systemctl --user enable --now discordbot.service

# 开机即使用户未 SSH 登录也启动（需要 sudo，只做一次）
sudo loginctl enable-linger $USER
```

**日常运维：**

```bash
systemctl --user status gscore discordbot
systemctl --user restart gscore          # 改插件 / 装依赖后
systemctl --user restart discordbot      # 打补丁后；重启 core 后也建议重启
journalctl --user -u gscore -f           # 跟日志
journalctl --user -u discordbot -f
```

Discord 发 `gs重启` 仍可重启 core；若用了 systemd，core 退出后会由 `Restart=always` 自动拉起。  
**重启 gscore 后建议再 `systemctl --user restart discordbot`**，避免 WebSocket 断连无响应。

> 不推荐再用 `screen` 长期挂进程；与 systemd 同时跑同一端口会冲突。

---

## 使用

| 场景       | 示例                                                          |
| ---------- | ------------------------------------------------------------- |
| 私聊       | `帮助`、`练度统计`、`绑定<特征码>`                            |
| 服务器频道 | `@机器人 帮助`                                                |
| 国际服数据 | 绑定 UID → 发送官方 DC 卡片图 `分析` → `角色面板`             |
| 国际服登录 | `登录` → 浏览器（默认已选国际服）→ 邮箱密码（可能需 Geetest） |
| 国际服体力 | 登录成功后发 `体力` 或 `mr`（走 `kuro-py`，非国服库街区 API） |

指令详情见插件内 `帮助` 图、本仓库 [国际服指令使用说明](discord_bot/command-guide/manual.md)，或 [官方插件文档](https://docs.sayu-bot.com/PluginsHelp/WutheringWavesUID.html)。

**Discord 与 `group_id`：** 桥接里 Discord 的 `group_id` = **频道 ID**（不是服务器 ID）。
绑定 / 登录 / 刷新面板等会把当前频道记入用户的绑定列表。
- **不受影响：** `角色面板`、`分析`、`练度统计`、`体力`、全服 `总排行` 等按用户 UID / 本地库，换频道或私聊一般照常。
- **群排行（Discord）：** `角色名排行` / 群练度排行会统计本 bot 下已绑定且本地有面板的用户（**私聊录入也算**），不再按频道隔离。
- **仍可能按频道隔离：** 部分群配置、其它群统计类指令；以实际行为为准。

**国际服说明：** 体力、先约电台、结晶波片等数据由 `kuro-py` 从 Kuro 国际服接口拉取，**并非**国服「库街区便笺」同一套 API。登录成功后应能出图；若只绑定 UID、未 `登录`，或 token 过期，会提示重新登录。周度游历等国际服暂无的字段会显示「国际服暂无数据」。

**总排行：** 接入全服总排行所需的 token / URL 为防止滥用**并未公开**，详情请咨询 [MoonShadow1976](https://github.com/MoonShadow1976)。

---

## 常见问题

| 现象                                                      | 处理                                                                                    |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `尤诺面板` / `练度统计` 无回复，gscore 只有 `[Receive]`   | 安装 `opencc`（见 [§1.1](#11-插件-python-依赖重要)），`gs重启`                          |
| 国际服网页登录「登入失敗」                                | 安装 `kuro-py`（见 §1.1），`gs重启`；账号需 Geetest 时在页面上完成验证                  |
| `体力` / `mr` 无回复或提示 token 失效                     | 确认已 `登录` 国际服账号；安装 `kuro-py` 并 `gs重启`                                    |
| 私聊/频道无回复，discordbot 有 `【发送】` 但无 `【接收】` | 确认 gscore 在监听 8765；**重启 discordbot**                                            |
| 发图报错 Snowflake                                        | 运行 `apply_snowflake_patch.py`，重启 discordbot                                        |
| 按钮「该交互失败」                                        | 运行 `apply_discord_button_patch.py`，重启 discordbot                                   |
| 重启 core 后 Discord 无响应                               | `systemctl --user restart discordbot`                                                   |
| VPS 重启后 bot 全挂、网页打不开                           | 确认已 `sudo loginctl enable-linger $USER`；`systemctl --user status gscore discordbot` |
| `pip install -U` 或重建 venv 后问题复发                   | 重新运行三个补丁脚本                                                                    |
| 私聊 / 另一频道 `莫宁排行` 人很少或只有自己               | 确认对方是否已绑定并录入该角色面板（`分析` / `刷新面板`）；全服用 `总排行` |

---

## 致谢

本仓库业务功能建立在社区长期维护的鸣潮插件之上，特别感谢：

- **[MoonShadow1976/WutheringWavesUID](https://github.com/MoonShadow1976/WutheringWavesUID)** — 唯一 upstream（业务插件主体）
- **[Wuthery](https://github.com/Wuthery)**（[spectro-pcap-server](https://github.com/Wuthery/spectro-pcap-server)、[kuro.py](https://github.com/Wuthery/kuro.py)）— 国际服 pcap 解析与登录 API
- **[gsuid_core](https://github.com/Genshin-bots/gsuid_core)** 与 **[nonebot-plugin-genshinuid](https://github.com/Genshin-bots/nonebot-plugin-genshinuid)** — 核心与多平台连接器
- 以及各攻略作者、数据与 OCR 相关开源项目（详见 upstream 历史贡献）

## 许可证

[GPL-3.0 License](LICENSE)
