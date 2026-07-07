# WutheringWavesUID

<p align="center">
  <a href="https://github.com/moonshadow1976/WutheringWavesUID"><img src="https://s2.loli.net/2024/10/08/ku3pLJBPoGjfQWq.png" width="256" height="256" alt="WutheringWavesUID"></a>
<h1 align = "center">WutheringWavesUID 3.0</h1>
<h4 align = "center">🚧支持OneBot(QQ)、QQ频道、微信、开黑啦、Telegram的全功能鸣潮Bot插件🚧</h4>
<div align = "center">
        <a href="https://docs.sayu-bot.com/" target="_blank">安装文档</a>   ·  
        <a href="https://docs.sayu-bot.com/PluginsHelp/WutheringWavesUID.html" target="_blank">指令列表</a>   ·  
        <a href="https://docs.sayu-bot.com/常见问题/">常见问题</a>
</div>

## 丨安装提醒

> **注意：该插件为[早柚核心(gsuid_core)](https://github.com/Genshin-bots/gsuid_core)的扩展
> 具体安装方式可参考[[快速开始](https://docs.sayu-bot.com/Started/InstallCore.html)]**
>
> **使用方式：**
> 如果已经是最新版本的 `gsuid_core`, ➡️在 `plugins`文件夹 **`git clone`本仓库**⬅️
> 后续可以直接对bot发送 `core全部更新`直接更新插件
> 如使用命令缺失素材可尝试使用命令 `ww下载全部资源`
>
> 支持国际服用户查询角色排行，由于国际服缺少库街区
> 国际服用户需基于 `Discord 图片识别`或 `PCAP文件抓包`使用 `WutheringWavesUID`
> 国际服用户使用 `ww分析`命令进行 `Discord 图片识别`前请先于控制台 `修改插件设定`处填充 [OCRspace API Key](https://ocr.space/OCRAPI)
>
> 支持NoneBot2 & HoshinoBot & ZeroBot & YunzaiBot的鸣潮Bot插件
>
> 🚧插件目前还在施工中，功能快速迭代中...🚧
>
> ✨如果需要添加其他鸣潮相关功能欢迎在issues中提出✨
>
> 🔥如有侵权请联系删除🔥

#### 丨说明

🕯️🕯️本仓库fork自[echo/WutheringWavesUID](https://github.com/tyql688/WutheringWavesUID)🕯️🕯️

> 继承并保持原有基础功能结构: 全功能开源，部分数据收集与展示对接私库服务器，除这部分外使用本仓库无需额外申请资格。
>
> 本仓库继echo放弃维护后由xinxiuzhu、lniuua、moonShadow1976维护
>
> 联系请使用[issue](https://github.com/MoonShadow1976/WutheringWavesUID/issues/new)，谢谢

## 丨其他

- 本项目仅供学习使用，请勿用于商业用途
- [GPL-3.0 License](https://github.com/moonshadow1976/WutheringWavesUID/blob/master/LICENSE)

## Discord 部署备忘（国际服 / 私域 Bot）

本 fork 在 [gsuid_core](https://github.com/Genshin-bots/gsuid_core) + [nonebot-plugin-genshinuid](https://github.com/Genshin-bots/nonebot-plugin-genshinuid) + [nonebot-adapter-discord](https://github.com/nonebot/adapter-discord) 之上运行鸣潮插件。典型架构：

```text
Discord → discordbot（NoneBot2）→ WebSocket → gsuid_core → WutheringWavesUID
```

### Message Content Intent：**建议关闭**

若只需要 **私聊** 或 **频道内 @ 机器人** 触发（与常见 QQ 群 bot 用法一致），**不必** 开启 Discord 的 Message Content Intent。

根据 [nonebot-adapter-discord 说明](https://github.com/nonebot/adapter-discord#discord_bots)，未开启时 Bot 在以下场景仍能收到完整消息内容：

- 私信（DM）
- 消息中 @ 了 Bot
- 回复了 Bot 的消息

开启 `message_content` 后，Bot 会读取频道内**所有**消息，容易误响应他人对话（例如同频道里的其他游戏 bot 指令），**私域小群不建议开启**。

**配置方式（两处都要一致）：**

1. [Discord Developer Portal](https://discord.com/developers/applications) → 你的应用 → **Bot** → 关闭 **Message Content Intent**
2. `~/discord_bot/.env` 中：

```json
"intent": {
  "guild_messages": true,
  "direct_messages": true,
  "message_content": false
}
```

修改 `.env` 后需 **重启 discordbot**（不必重启 gsuid_core）。

### 插件前缀（gshub / 网页控制台）

与「@ 机器人 + 无前缀指令」对齐时，在 WutheringWavesUID 插件配置中建议：

- `disable_force_prefix`: `true`
- `allow_empty_prefix`: `true`

改完后需 **重启 gsuid_core**（Discord 发 `gs重启`，或 SSH 重启 gscore）。

用法示例：

| 场景       | 示例               |
| ---------- | ------------------ |
| 私聊       | `帮助`、`练度统计` |
| 服务器频道 | `@守岸人 帮助`     |

### 进程与排错

VPS 上通常用两个 `screen` 会话：

| screen 名    | 启动命令（在对应目录）                                        |
| ------------ | ------------------------------------------------------------- |
| `gscore`     | `cd ~/gsuid_core && python3.13 -m uv run core --host 0.0.0.0` |
| `discordbot` | `cd ~/discord_bot && .venv/bin/nb run`                        |

**检查 gscore 是否在跑**（不要只搜 `uv run core`，网页控制台重启时可能是 `python -m gsuid_core.core`）：

```bash
ss -tlnp | grep 8765
ps aux | grep gsuid_core | grep -v grep
```

| 现象                                                      | 处理                                                             |
| --------------------------------------------------------- | ---------------------------------------------------------------- |
| 私聊/频道无回复，discordbot 有 `【发送】` 但无 `【接收】` | 先确认 gscore 在监听 8765；再 **重启 discordbot** 重连 WebSocket |
| `address already in use` (8765)                           | 已有 core 在跑，勿重复启动；`kill` 旧 PID 后只启一个             |
| 只重启了 gscore                                           | **务必再重启 discordbot**，否则 WS 可能断连不恢复                |
| 停 nonebot 要按两次 Ctrl+C                                | 第一次优雅退出，第二次强制退出，属正常现象                       |

配置文件路径：`~/discord_bot/.env`（单层目录 `~/discord_bot`，不要套 `discord_bot/discord_bot`）。

### GenshinUID 补丁（`discord_bot/patches/`）

`nonebot-plugin-genshinuid` 对 Discord 有几处已知问题，需在 **discord_bot 的 venv 内**对 site-packages 打补丁。每次 **重建 `.venv` 或升级 GenshinUID 后都要重新执行**。

| 脚本 | 作用 | 典型现象（未打补丁时） |
|------|------|------------------------|
| [`apply_snowflake_patch.py`](discord_bot/patches/apply_snowflake_patch.py) | 修复附件里的 Snowflake 序列化 | 带图指令失败：`Encoding objects of type Snowflake is unsupported` |
| [`apply_discord_button_patch.py`](discord_bot/patches/apply_discord_button_patch.py) | 修复帮助页按钮 ACK | 点蓝色按钮显示「该交互失败」 |
| [`apply_discord_reply_patch.py`](discord_bot/patches/apply_discord_reply_patch.py) | 回复引用原指令，不 @ 用户 | 回复无灰色引用条；多人同时发指令时难以区分 |

```bash
cd ~/discord_bot
~/discord_bot/.venv/bin/python patches/apply_snowflake_patch.py
~/discord_bot/.venv/bin/python patches/apply_discord_button_patch.py
~/discord_bot/.venv/bin/python patches/apply_discord_reply_patch.py
```

打完补丁需 **重启 discordbot**。`reply` 补丁效果：像 Discord 右键「回复」一样显示你的原指令，正文不再 @ 你（频道与私聊均适用）。

### OCR.space（国际服 Discord 卡片识别）

国际服缺少库街区，**角色面板截图识别**（如 `分析` / `ww分析`）依赖 [OCR.space](https://ocr.space/OCRAPI) API，由插件 `wutheringwaves_analyzecard` 调用。

**配置方式：** 在 gsuid_core **网页控制台** → WutheringWavesUID 插件配置 → `OCRspaceApiKeyList`，填入你在 OCR.space 注册获得的 API Key（可填多个，插件会轮询）。

**使用注意：**

- VPS 需能访问 `api.ocr.space`（出站网络正常）
- 游戏内卡片需为**中文界面**（默认语言 `cht`）；英文卡会提示 `Please use chinese card!`
- 可选配置 `CardImgCheck`：开启后对声骸图标做额外校验（国际服 DC 卡片，默认 `False`）
- 发图方式：私聊或频道 @ 机器人后发送角色详情截图 + 指令；Discord 附件 URL 由插件自动解析

未配置 Key 时，识别会提示 `OCRspace API密钥未配置，请检查控制台`。

## 致谢

- [Wuyi无疑](https://github.com/KimigaiiWuyi) 和 [ECHO](https://github.com/tyql688)
- [鸣潮声骸评分工具](http://asfaz.cn/mingchao/rule.html) 鸣潮声骸评分工具
- [waves-plugin](https://github.com/erzaozi/waves-plugin) Yunzai 鸣潮游戏数据查询插件
- [Yunzai-Kuro-Plugin](https://github.com/TomyJan/Yunzai-Kuro-Plugin) Yunzai 库洛插件
- [Kuro-API-Collection](https://github.com/TomyJan/Kuro-API-Collection) 库街区 API 文档
- [ocr.space_code_example](https://github.com/Zaargh/ocr.space_code_example) OCR.space 示例
- [Wuthery](https://wuthery.com/)与[YashajinAlice](https://github.com/YashajinAlice) 的支持
- [wuwabot_reader](https://github.com/TedIwaArdN/wuwabot_reader) 图像匹配逻辑
- [ScoreQuery](https://github.com/alone-art/ScoreQuery) 声骸评分
- 特别鸣谢以下攻略作者 (排名无先后顺序)
  - [Moealkyne](https://www.taptap.cn/user/533395803)
  - [小沐XMu](https://www.kurobbs.com/person-center?id=10450567)
  - [金铃子攻略组](https://space.bilibili.com/487275027)
  - [吃我无痕](https://space.bilibili.com/347744)
  - [小羊早睡不遭罪](https://space.bilibili.com/37331716)
  - [結星](https://www.kurobbs.com/person-center?id=10015697)
