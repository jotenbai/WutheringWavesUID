from gsuid_core.logger import logger
from gsuid_core.server import on_core_start

from ..utils.zh_convert import install_msg_process_t2s
from ..wutheringwaves_resource import startup
from .. import wutheringwaves_gallery as _ww_gallery  # noqa: F401  # 注册「更新图集」

# 插件加载时挂上：指令匹配前统一繁体→简体
install_msg_process_t2s()


@on_core_start
async def all_start():
    logger.info("[鸣潮] 启动中...")
    try:
        import asyncio

        from ..utils.damage.register_char import register_char
        from ..utils.damage.register_echo import register_echo
        from ..utils.damage.register_weapon import register_weapon
        from ..utils.limit_user_card import load_limit_user_card
        from ..utils.map.damage.register import register_damage, register_rank
        from ..utils.queues import init_queues
        from ..wutheringwaves_config import WutheringWavesConfig

        # 注册
        register_weapon()
        register_echo()
        register_damage()
        register_rank()
        register_char()

        # 初始化任务队列
        init_queues()

        # 加载角色极限面板
        card_list = await load_limit_user_card()
        logger.info(f"[鸣潮][加载角色极限面板] 数量: {len(card_list)}")

        await startup()

        if WutheringWavesConfig.get_config("GallerySyncOnStart").data:
            from ..utils.gallery_sync import sync_gallery_to_local

            async def _gallery_sync_bg():
                try:
                    await sync_gallery_to_local()
                except Exception:
                    logger.exception("[鸣潮] 启动时图集同步失败")

            logger.info("[鸣潮] 图集同步任务已在后台启动")
            asyncio.create_task(_gallery_sync_bg())
    except Exception as e:
        logger.exception(e)

    logger.success("[鸣潮] 启动完成✅")
