import nonebot
from nonebot.adapters.discord import Adapter as DiscordAdapter

nonebot.init()
nonebot.get_driver().register_adapter(DiscordAdapter)
nonebot.load_plugin("GenshinUID")
nonebot.run()
