# WutheringWavesUID for Discord

基于 [gsuid_core](https://github.com/Genshin-bots/gsuid_core) 的鸣潮 Bot 插件，本仓库在 upstream 基础上**侧重国际服 + Discord 桥接部署**（`discord_bot/` 目录）。

私聊或 `@机器人` 发送「帮助」「练度统计」等指令，体验可参考 [nahida-examples](https://github.com/gamer-mitsuha/nahida-examples) 一类无前缀用法。

## 架构

```text
Discord
  → nonebot-adapter-discord
  → nonebot-plugin-genshinuid（WebSocket 连接器）
  → gsuid_core
  → WutheringWavesUID（本仓库插件）
```

| 组件                                                     | 说明                                        |
| -------------------------------------------------------- | ------------------------------------------- |
| [gsuid_core](https://github.com/Genshin-bots/gsuid_core) | 核心，负责加载插件与 Web 控制台             |
| `WutheringWavesUID/`                                     | 鸣潮业务逻辑（角色面板、练度、OCR 等）      |
| `discord_bot/`                                           | NoneBot2 桥接层，连接 Discord 与 gsuid_core |

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
- **OCRspace API Key**（国际服 `分析` / DC 卡片识别需要）

修改插件配置后需 **重启 gsuid_core**（Discord 发 `gs重启`，或重启 core 进程）。

更新插件：

```bash
cd ~/gsuid_core/gsuid_core/plugins/WutheringWavesUID
git pull
# 然后 gs重启
```

---

## 二、Discord 部署（`discord_bot/`）

VPS 推荐目录：`~/discord_bot`（单层目录，在此目录执行 `nb run`）。

### 2.1 Discord Developer Portal

在 [Discord 开发者门户](https://discord.com/developers/applications) 创建应用并添加 Bot：

- 开启 **Message Content Intent**（否则频道内普通消息收不到）
- 建议权限：View Channels、Send Messages、Read Message History、Attach Files、Embed Links
- 用 OAuth2 URL Generator 生成邀请链接；**服主或有「管理服务器」权限的人**可用该链接把 Bot 安装到任意服务器（不限于你自己创建的服）

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
  "gsuid_core_host": "127.0.0.1",
  "gsuid_core_port": 8765,
  "gsuid_core_ws_token": ""
}
```

门户里开了 Message Content Intent 后，`.env` 里也必须写 `message_content: true`。

### 2.3 安装与启动

```bash
cd ~/discord_bot
uv sync
# 若无 uv：python3.12 -m venv .venv && .venv/bin/pip install -e .

# 必需补丁（升级 genshinuid 后需重跑）
.venv/bin/python3 patches/apply_snowflake_patch.py
.venv/bin/python3 patches/apply_discord_button_patch.py

.venv/bin/python3 -m nb run
```

若 `source .venv/bin/activate` 报错，全程用 `.venv/bin/python3` 即可。

### 2.4 补丁说明

当前 `nonebot-plugin-genshinuid` 在 Discord 上有两处已知问题，本仓库提供脚本修补 **venv 内已安装的 GenshinUID**：

| 脚本                                    | 修复内容                               |
| --------------------------------------- | -------------------------------------- |
| `patches/apply_snowflake_patch.py`      | 发带附件/图片消息时 Snowflake 编码错误 |
| `patches/apply_discord_button_patch.py` | 帮助页等按钮点击「该交互失败」         |

### 2.5 后台常驻（screen 示例）

```bash
screen -S gscore
cd ~/gsuid_core && python3.13 -m uv run core --host 0.0.0.0
# Ctrl+A 再 D 脱离

screen -S discordbot
cd ~/discord_bot && .venv/bin/python3 -m nb run
# Ctrl+A 再 D 脱离
```

**重启 gsuid_core 后，请同时重启 discordbot**，否则 WebSocket 会断连无响应。

---

## 使用

| 场景       | 示例                                              |
| ---------- | ------------------------------------------------- |
| 私聊       | `帮助`、`练度统计`、`绑定<特征码>`                |
| 服务器频道 | `@机器人 帮助`                                    |
| 国际服数据 | 绑定 UID → 发送官方 DC 卡片图 `分析` → `角色面板` |

指令详情见插件内 `帮助` 图，或 [官方插件文档](https://docs.sayu-bot.com/PluginsHelp/WutheringWavesUID.html)。

**邀请他人使用**：OAuth2 邀请链接加服务器；同服成员可在成员列表对 Bot 点「发消息」私聊。未验证 Bot 不会出现在应用商店，但邀请链接仍可用（未验证约 100 服上限）。

---

## 常见问题

| 现象                        | 处理                                                     |
| --------------------------- | -------------------------------------------------------- |
| 群里不回复，私聊正常        | `.env` 缺 `message_content: true`；或改前缀后未重启 core |
| 发图报错 Snowflake          | 运行 `apply_snowflake_patch.py`，重启 discordbot         |
| 按钮「该交互失败」          | 运行 `apply_discord_button_patch.py`，重启 discordbot    |
| 重启 core 后 Discord 无响应 | 同时重启 discordbot                                      |
| `pip install -U` 后问题复发 | 重新运行两个补丁脚本                                     |

---

## 致谢

本仓库业务功能建立在社区长期维护的鸣潮插件之上，特别感谢：

- **[CM-Edelweiss/WutheringWavesUID](https://github.com/CM-Edelweiss/WutheringWavesUID)** — 早期插件基础
- **[MoonShadow1976/WutheringWavesUID](https://github.com/MoonShadow1976/WutheringWavesUID)** — 当前主要 upstream 维护
- **[gsuid_core](https://github.com/Genshin-bots/gsuid_core)** 与 **[nonebot-plugin-genshinuid](https://github.com/Genshin-bots/nonebot-plugin-genshinuid)** — 核心与多平台连接器
- 以及各攻略作者、数据与 OCR 相关开源项目（详见 upstream 历史贡献）

## 许可证

[GPL-3.0 License](LICENSE)
