# discord_bot

NoneBot2 桥接层：Discord ↔ [gsuid_core](https://github.com/Genshin-bots/gsuid_core) ↔ [WutheringWavesUID](../WutheringWavesUID)。

VPS 部署路径：`~/discord_bot`（单层，不要再套 `discord_bot/discord_bot` 才 `nb run`）。

## 架构

```
Discord → nonebot-adapter-discord → nonebot-plugin-genshinuid → WebSocket → gsuid_core → WutheringWavesUID
```

## 本地 ↔ VPS 同步

`scp .../discord_bot/*` **不会**拷贝以 `.` 开头的文件（shell 通配符规则）。需要显式指定：

```powershell
# 在仓库根目录（Windows PowerShell）
cd "e:\编程\WutheringWavesUID_for_discord"

# 非隐藏文件（已做过一次）
scp -r admin@YOUR_VPS:~/discord_bot/* ./discord_bot/

# 还要单独拉：源码包、gitignore（不要拉 .env / .venv）
scp -r admin@YOUR_VPS:~/discord_bot/discord_bot ./discord_bot/
scp admin@YOUR_VPS:~/discord_bot/.gitignore ./discord_bot/
```

**切勿** `scp` 到本地的文件：`.env`（Token）、`.venv/`（在 VPS 上 `uv sync` 重建）。

## VPS 首次 / 恢复部署

```bash
cd ~/discord_bot
uv sync          # 或：python3.12 -m venv .venv && pip install -e .
cp .env.example .env   # 若 .env 丢失，从模板手填 Token
source .venv/bin/activate

cd ~/discord_bot
source .venv/bin/activate   # 若 activate 报错，改用下一行的 .venv/bin/python3
.venv/bin/python3 patches/apply_snowflake_patch.py
.venv/bin/python3 patches/apply_discord_button_patch.py

nb run
```

## Discord Developer Portal

- **Message Content Intent**：门户开启 + `.env` 里 `message_content: true`
- 建议权限：View Channels, Send Messages, Read Message History, Attach Files, Embed Links

## gsuid_core 插件前缀

gshub → WutheringWavesUID：`disable_force_prefix: true`、`allow_empty_prefix: true` → 保存后 `gs重启`。

## 已知问题

### Snowflake 编码错误

`TypeError: Encoding objects of type Snowflake is unsupported` → 运行 [`patches/apply_snowflake_patch.py`](patches/apply_snowflake_patch.py)。

### 帮助页按钮「该交互失败」

QQ 正常、Discord 点蓝色按钮失败：GenshinUID 对组件交互误用了 `PONG`，且 ACK 可能在 `ws.ping()` 之后才发出导致超时。运行 [`patches/apply_discord_button_patch.py`](patches/apply_discord_button_patch.py) 后重启 `discordbot`。

### 重启 gscore 后 Discord 无响应

重启 core 后请同时重启 discordbot：`screen -r discordbot` → Ctrl+C → `cd ~/discord_bot && nb run`。

### xterminal 拖文件

同名文件夹拖动可能移到 `~/.xterminal/discord_bot/`，不会合并；整理目录用 SSH `mv`，动刀前 `cp -a ~/discord_bot ~/discord_bot.bak`。

## NoneBot 模板说明

本工程由 `nb create` 生成。插件目录：`discord_bot/plugins`。详见 [NoneBot 文档](https://nonebot.dev/)。

## 相关链接

- [gsuid_core](https://github.com/Genshin-bots/gsuid_core)
- [nonebot-plugin-genshinuid](https://github.com/Genshin-bots/nonebot-plugin-genshinuid)
- [nonebot-adapter-discord](https://github.com/nonebot/adapter-discord)
