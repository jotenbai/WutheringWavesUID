"""init"""

from gsuid_core.sv import Plugins

Plugins(name="WutheringWavesUID", force_prefix=["ww"], allow_empty_prefix=False)

# 指令匹配前统一繁体→简体（幂等；start 模块也会再挂一次）
try:
    from .utils.zh_convert import install_msg_process_t2s

    install_msg_process_t2s()
except Exception:
    pass
