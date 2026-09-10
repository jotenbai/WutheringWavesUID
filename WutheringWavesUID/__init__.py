"""init"""

from gsuid_core.sv import Plugins

Plugins(name="WutheringWavesUID", force_prefix=["ww"], allow_empty_prefix=False)

# 指令匹配前统一繁体→简体（幂等；start 模块也会再挂一次）
try:
    from .utils.zh_convert import install_msg_process_t2s

    install_msg_process_t2s()
except Exception:
    pass

# Discord 私聊：未完成服务器归属时一律提示去频道（须在繁简转换之后）
try:
    from .utils.discord_dm_gate import install_discord_dm_affiliation_gate

    install_discord_dm_affiliation_gate()
except Exception:
    pass
