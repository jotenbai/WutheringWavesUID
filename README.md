# WutheringWavesUID for Discord

本仓库在 [MoonShadow1976/WutheringWavesUID](https://github.com/MoonShadow1976/WutheringWavesUID) 基础上**侧重国际服 + Discord 桥接部署**（`discord_bot/` 目录）。

**主要目的：** 帮助玩家把握角色培养进度（面板、练度、声骸评分等）。国际服新手可先看 [指令使用说明与示例](discord_bot/command-guide/manual.md)。

私聊或 `@机器人` 发送「帮助」「练度统计」等指令，体验可参考 [nahida-examples](https://github.com/gamer-mitsuha/nahida-examples) 一类无前缀用法。

### 怎么用（三选一）

| 方式             | 说明                                                                                                                                                       |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **加入支持服**   | 进入维护者的 [Discord 服务器](https://discord.com/invite/eWnWyGqEXM)，在频道内（或完成归属后私聊）使用「守岸人」                                           |
| **邀请到你的服** | 用 [邀请链接](https://discord.com/oauth2/authorize?client_id=1482666240140116099) 把「守岸人」加进你的服务器。别服数据会进同一套维护者服务器，详见隐私政策 |
| **自己部署**     | 按下文在 VPS 上部署本仓库，在 Discord 开发者门户**新建自己的 Bot**，使用你自己的 Token 与配置（数据与维护者实例互不相通）                                  |

个人兴趣维护，非官方、非商业；**不保证**长期可用。  
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

上表是**消息链路**，不是 VPS 上的文件夹树。本仓库里 `discord_bot/` 只是文档与模板的存放位置；**真正跑桥接时**，应单独建一个与 gsuid_core **平级**的运行目录（常见为 `~/discord_bot`），把模板拷进去再配 `.env`，不要指望在「插件仓内部的 `discord_bot/`」里直接当生产进程目录。

### VPS 目录参考（与本仓库布局不同）

```text
~/                          # 例：/home/admin
├── gsuid_core/             # 独立安装的 gsuid_core（systemd: gscore）
│   ├── .venv/
│   └── gsuid_core/
│       └── plugins/
│           └── WutheringWavesUID/   # 本仓库整仓 clone（插件入口在仓根 __init__.py）
│               ├── WutheringWavesUID/   # Python 业务包
│               ├── discord_bot/         # 模板 / 文档 / 补丁脚本（随仓；不是运行目录）
│               ├── README.md
│               └── ...
└── discord_bot/            # 另建的桥接运行目录（systemd: discordbot）
    ├── .venv/
    ├── .env                # Bot Token、Intent、免 @ 频道等（勿提交）
    ├── patches/            # 从本仓 discord_bot/patches 拷来并 apply
    └── ...
```

要点：

- **插件**跟 gsuid_core 走：更新 = 在 `plugins/WutheringWavesUID` 里 `git pull`，再 `restart gscore`。
- **桥接**跟 `~/discord_bot` 走：`.env` 只放这里；改补丁后 `restart discordbot`。
- 仓库内的 `discord_bot/` ≠ VPS 上的 `~/discord_bot`：前者是随插件仓的模板；后者是独立运行的桥接副本。

## 前置要求

- 一台可公网访问的 Linux VPS（或云服务器）
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

Web 控制台默认 `http://<主机>:8765/app`（域名反代则为 `https://core.你的域名/app/`）。改完配置后多数项需 **重启 gsuid_core**（Discord 发 `core重启`，或 `systemctl --user restart gscore`）才生效。

### 网页控制台推荐设置

配置分两处，国际服 Discord 自用建议如下（**推荐**列按本 fork 小服场景；你自己改过的以实际为准）。

#### A. 插件配置 → WutheringWavesUID

前缀两项一般在该插件的「插件 / 前缀」相关页；其余在插件业务配置里。

| 变量名 / 控制台名                                   | 功能简述                                                                                         | 推荐                                 |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------ |
| `disable_force_prefix`（禁用强制前缀）              | 不用 `ww` 等前缀也能触发指令                                                                     | **开**                               |
| `allow_empty_prefix`（允许空命令前缀）              | 允许无前缀匹配                                                                                   | **开**                               |
| `WavesLoginUrl`（鸣潮登录 url）                     | `登录` / `上传pcap` 等网页根地址；填如 `https://core.你的域名`（勿尾斜杠）。空则易拼成 `IP:8765` | **必填域名**                         |
| `OCRspaceApiKeyList`                                | 国际服 `分析` / DC 角色卡 OCR                                                                    | **填**（要用分析时）                 |
| `botData`（bot排行查询开关）                        | 是否开放 `bot排行` / `bot持有率` 等「本机器人全体绑定用户」层                                    | **开**（Discord 分层需要）           |
| `WavesRankUrl` / `WavesToken`（全排行 url / token） | `角色名总排行` 远端榜；`刷新面板` 上传也依赖                                                     | 要用总排行再填；勿公开               |
| `CharCardRefresh`（角色面板自动刷新）               | 国服查面板时自动刷；国际服主要靠 pcap/`分析`                                                     | 可保持默认开                         |
| `AtCheck`（开启可以艾特查询）                       | 允许 @某人 查对方数据                                                                            | 按需，默认开                         |
| `HideUid`（隐藏 uid）                               | 出图是否隐藏特征码                                                                               | 按需                                 |
| `WavesQRLogin` / `WavesLoginForward`                | 登录链变二维码 / 转发消息                                                                        | Discord 建议**关**（直接发链接更稳） |
| `StaminaPush`（体力推送）                           | 体力到阈值私聊/群推送                                                                            | 小服可**关**，省打扰                 |
| `MaxBindNum`                                        | 未登录时可绑定特征码上限                                                                         | 默认即可                             |
| `RankUseToken`（有 token 才能进排行）               | 收紧进本地排行条件                                                                               | 自用一般**关**                       |
| `AllowImportGachaLogs`                              | 允许用户直接导入抽卡记录                                                                         | 一般**关**                           |
| `CardImgCheck`（国际服 dc 卡片声骸图标识别）        | 分析卡片时额外认声骸图标                                                                         | 按需                                 |

#### B. 管理核心 → 框架配置

| 控制台项（常见归在「自动更新」等） | 功能简述                         | 推荐                                 |
| ---------------------------------- | -------------------------------- | ------------------------------------ |
| 自动更新 Core / 自动更新插件       | 定时 `git pull` 代码             | 自用可开；开则务必配下面「自动重启」 |
| 自动重启 Core（约 4:40）           | 更新后重启进程，否则新代码不生效 | 若开了自动更新 → **开**              |
| 自动更新时通知主人                 | 凌晨把更新日志私聊推给主人       | **关**（免 Discord 刷屏）            |
| 主人 / masters                     | 主人 Discord 雪花 ID（权限最高） | **填你的 ID**；改后须重启 core       |

主人 ID、黑名单等若在「权限 / 用户」页，以控制台实际菜单为准；改 masters 后必须重启 gscore。

### 1.1 插件 Python 依赖（重要）

gsuid_core 启动时会尝试安装插件 `requirements.txt` 中的依赖，但在部分环境（如 Python 3.13 + 仅 `uv` 管理 core）下，**个别包可能未装进 core 的 venv**，导致部分子模块导入失败、对应指令静默无回复。

插件根目录 [`requirements.txt`](requirements.txt) 当前包含：

| 包名      | 用途                                               | 未安装时的典型现象                                    |
| --------- | -------------------------------------------------- | ----------------------------------------------------- |
| `opencc`  | 指令/OCR 繁体转简体（`zh_convert`、`analyzecard`） | `尤诺面板`、`练度统计` 等无触发；繁体指令无法自动转简 |
| `kuro-py` | 国际服登录与体力等 API（`kuro` 模块）              | 网页登录「登入失敗」；`体力` / `mr` 无数据或报错      |

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

- 建议权限：View Channels、Send Messages、Read Message History、Attach Files、Embed Links
- 用 OAuth2 URL Generator 生成邀请链接
- **指定频道免 @（可选，推荐）：** 完整步骤见 [§2.5](#25-免--频道白名单推荐)（Message Content Intent + `DISCORD_NO_MENTION_CHANNELS` + 免 @ 补丁）。**不要**只靠服务器「整合 → 频道」限制。
- 若不用免 @：Portal 与 `.env` 可保持 `message_content: false`（私聊、@、回复机器人仍有正文）

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
        "message_content": true
      }
    }
  ],
  "DISCORD_NO_MENTION_CHANNELS": "频道雪花ID",
  "gsuid_core_host": "127.0.0.1",
  "gsuid_core_port": 8765,
  "gsuid_core_ws_token": ""
}
```

门户与 `.env` 中 `message_content` 设置须一致。免 @ 频道 ID 填入 `DISCORD_NO_MENTION_CHANNELS`（可多个，逗号分隔）。

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
~/discord_bot/.venv/bin/python patches/apply_discord_no_mention_channel_patch.py
~/discord_bot/.venv/bin/python patches/apply_discord_guild_as_group_patch.py

~/discord_bot/.venv/bin/nb run
# 或：~/discord_bot/.venv/bin/python bot.py
```

若 `source .venv/bin/activate` 报错，全程用 `~/discord_bot/.venv/bin/python` / `.venv/bin/nb` 即可。

### 2.4 补丁说明

`nonebot-plugin-genshinuid` 对 Discord 有几处已知问题，补丁脚本会修改 **venv 内已安装的 GenshinUID**：

| 脚本                                                                                                         | 作用                                                          | 典型现象（未打补丁时）                                  |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- | ------------------------------------------------------- |
| [`apply_snowflake_patch.py`](discord_bot/patches/apply_snowflake_patch.py)                                   | 修复附件 Snowflake 序列化                                     | `Encoding objects of type Snowflake is unsupported`     |
| [`apply_discord_button_patch.py`](discord_bot/patches/apply_discord_button_patch.py)                         | 修复帮助页按钮 ACK                                            | 点按钮「该交互失败」                                    |
| [`apply_discord_reply_patch.py`](discord_bot/patches/apply_discord_reply_patch.py)                           | 回复引用原指令，不 @ 用户                                     | 无灰色引用条；多人同时发指令难区分                      |
| [`apply_discord_no_mention_channel_patch.py`](discord_bot/patches/apply_discord_no_mention_channel_patch.py) | 白名单频道免 @；其它频道仍须 @；忽略「只 @ 了别的 bot」的消息 | 开 Intent 后全频道误触发；或免 @ 无响应；与纳西妲等抢答 |
| [`apply_discord_guild_as_group_patch.py`](discord_bot/patches/apply_discord_guild_as_group_patch.py)         | `sender.discord_guild_id`：Discord 服务器≈QQ 群               | 群排行/群持有率仍按频道隔离或私聊误计入群               |

打完补丁需 **重启 discordbot**。升级 / 重建 venv 后**五个**补丁都要重跑。

### 2.5 免 @ 频道（白名单，推荐）

默认频道里必须真正 `@机器人` 才有正文（Message Content Intent 关闭时）。若希望某个频道像私聊一样直接发 `帮助`、`分析`，按下面做——**Intent 全局开启 + 代码白名单**，其它频道仍须 @。

**步骤：**

1. Discord 里建专用频道（建议命名如 `鸣潮bot专用`），右键 → **复制频道 ID**（需开开发者模式）。
2. [开发者门户](https://discord.com/developers/applications) → Bot → 打开 **Message Content Intent** → Save。  
   Intent 一重连即对已邀请的服务器生效，**一般不必重新邀请** bot。
3. 编辑运行目录 `~/discord_bot/.env`（与门户一致）：

```env
# DISCORD_BOTS 的 JSON 里：
# "message_content": true

# 免 @ 频道雪花，多个用英文逗号分隔
DISCORD_NO_MENTION_CHANNELS=123456789012345678
```

4. 打补丁并重启桥接：

```bash
cd ~/discord_bot
.venv/bin/python patches/apply_discord_no_mention_channel_patch.py
systemctl --user restart discordbot   # 或你的启动方式
```

5. 在该频道**不 @** 发 `帮助` 应有回复；其它频道不 @ 应无响应，`@机器人 帮助` 仍正常。

**注意：**

- **不要**用服务器「整合 → 频道」把 bot 限制成只能进一个频道——那主要管斜杠命令；踢出其它频道会导致那里连 `@` 也不能用。
- 免 @ 频道里机器人会处理该频道普通文字；已忽略「只 @ 了其它机器人」的消息，减少与纳西妲等抢答。仍建议频道名写清用途，原神指令放别的频道。
- 补丁改的是 **venv 里的 GenshinUID**，不是本仓插件业务代码；`pip install -U nonebot-plugin-genshinuid` 后须重跑补丁。
- 改 Intent / 白名单 **不用**踢服重邀；只有缺具体权限（发图等）时才在该服补权限或换带权限的邀请链接。

### 2.6 OCR.space（国际服 Discord 卡片识别）

国际服缺少库街区，**角色面板截图识别**（如 `分析` / `ww分析`）依赖 [OCR.space](https://ocr.space/OCRAPI) API。

**配置：** gsuid_core 网页控制台 → WutheringWavesUID → `OCRspaceApiKeyList`，填入 API Key（可多个，插件轮询）。

**注意：**

- VPS 需能访问 `api.ocr.space`
- 游戏内卡片须为**中文界面**（默认 `cht`）；英文卡会提示 `Please use chinese card!`
- 可选 `CardImgCheck`：声骸图标额外校验（默认 `False`）
- 私聊或频道 @ 机器人后，发角色详情截图 + 指令

### 2.7 后台常驻（systemd，推荐）

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
| 免 @ 频道  | 配置见 [§2.5](#25-免--频道白名单推荐)；频道内可直接 `帮助`    |
| 国际服数据 | 绑定 UID → 发送官方 DC 卡片图 `分析` → `角色面板`             |
| 国际服登录 | `登录` → 浏览器（默认已选国际服）→ 邮箱密码（可能需 Geetest） |
| 国际服体力 | 登录成功后发 `体力` 或 `mr`（走 `kuro-py`，非国服库街区 API） |

指令详情见插件内 `帮助` 图、本仓库 [国际服指令使用说明](discord_bot/command-guide/manual.md)，或 [官方插件文档](https://docs.sayu-bot.com/PluginsHelp/WutheringWavesUID.html)。

**Discord 与群归属：**

- 桥接回信用的 `group_id` 仍是**频道 ID**（发消息必需）。
- **逻辑群**（`群排行` / `群持有率` / WavesBind 归属）= **Discord 服务器 ID（guild）**，与 QQ 群对齐；经 `sender.discord_guild_id` + 补丁 `apply_discord_guild_as_group_patch.py`。
- **bot 层**：本机全部绑定用户（跨服务器 + 私聊录入）。
- **私聊**：不计入任何「群\*」；可用 `bot排行` / `bot持有率`。
- **多服**：同一 Discord 用户在 A、B 两服都用过，可同时属于两服的群统计（与 QQ 多群相同）。
- **国际服群/bot 持有率**：仅统计有 **pcap** 的 UID（避免只「分析」热门角造成虚高）；伤害/评分排行仍可用本地面板（含分析）。

旧绑定里可能残留历史**频道** ID；用户在服务器频道再发一次会触发的指令（绑定 / 群排行 / 群持有率等）会把 **guild** 写入归属。

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
| `pip install -U` 或重建 venv 后问题复发                   | 重新运行**五个**补丁脚本（含免 @、guild 归属）                                          |
| 免 @ 频道仍必须 @ / 开 Intent 后乱触发                    | 查 §2.5：门户与 `.env` 的 `message_content`、白名单 ID、是否重跑免 @ 补丁并重启         |
| 免 @ 频道里 @纳西妲 也被守岸人回                          | 确认已打免 @ 补丁 **v3+**（忽略只 @ 其它 bot）；频道建议专用于鸣潮                      |
| 私聊 / 另一频道 `莫宁排行` 人很少或只有自己               | 确认对方是否已绑定并录入该角色面板（`分析` / `刷新面板`）；全服用 `总排行`              |

---

## 致谢

本仓库业务功能建立在社区长期维护的鸣潮插件之上，特别感谢：

- **[MoonShadow1976/WutheringWavesUID](https://github.com/MoonShadow1976/WutheringWavesUID)** — 唯一 upstream（业务插件主体）
- **[Wuthery](https://github.com/Wuthery)**（[spectro-pcap-server](https://github.com/Wuthery/spectro-pcap-server)、[kuro.py](https://github.com/Wuthery/kuro.py)）— 国际服 pcap 解析与登录 API
- **[gsuid_core](https://github.com/Genshin-bots/gsuid_core)** 与 **[nonebot-plugin-genshinuid](https://github.com/Genshin-bots/nonebot-plugin-genshinuid)** — 核心与多平台连接器
- 以及各攻略作者、数据与 OCR 相关开源项目（详见 upstream 历史贡献）

## 许可证

[GPL-3.0 License](LICENSE)
