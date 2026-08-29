from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path
import random
import threading
from typing import Literal

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.image_tools import crop_center_img
from gsuid_core.utils.image.utils import sget
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
)

from ..utils.database.models import WavesUserAvatar
from ..utils.resource.RESOURCE_PATH import (
    AVATAR_PATH,
    CUSTOM_CARD_PATH,
    CUSTOM_MR_CARD_PATH,
    ROLE_PILE_PATH,
    SHARE_BG_PATH,
    WEAPON_PATH,
)
from ..wutheringwaves_config import WutheringWavesConfig

ICON = Path(__file__).parent.parent.parent / "ICON.png"
TEXT_PATH = Path(__file__).parent / "texture2d"
GREY = (216, 216, 216)
BLACK_G = (40, 40, 40)
YELLOW = (255, 200, 1)
RED = (255, 0, 0)
BLUE = (1, 183, 255)
GOLD = (224, 202, 146)
SPECIAL_GOLD = (234, 183, 4)
AMBER = (204, 140, 0)
GREEN = (144, 238, 144)

# 冷凝-凝夜白霜
WAVES_FREEZING = (53, 152, 219)
# 热熔-熔山裂谷
WAVES_MOLTEN = (186, 55, 42)
# 导电-彻空冥雷
WAVES_VOID = (185, 106, 217)
# 气动-啸谷长风
WAVES_SIERRA = (22, 145, 121)
# 衍射-浮星祛暗
WAVES_CELESTIAL = (241, 196, 15)
# 湮灭-沉日劫明
WAVES_SINKING = (132, 63, 161)
# 治疗-隐世回光
WAVES_REJUVENATING = (45, 194, 107)
# 辅助-轻云出月
WAVES_MOONLIT = (149, 165, 166)
# 攻击-不绝余音
WAVES_LINGERING = (52, 73, 94)

WAVES_ECHO_MAP = {
    "凝夜白霜": WAVES_FREEZING,
    "熔山裂谷": WAVES_MOLTEN,
    "彻空冥雷": WAVES_VOID,
    "啸谷长风": WAVES_SIERRA,
    "浮星祛暗": WAVES_CELESTIAL,
    "沉日劫明": WAVES_SINKING,
    "隐世回光": WAVES_REJUVENATING,
    "轻云出月": WAVES_MOONLIT,
    "不绝余音": WAVES_LINGERING,
}

WAVES_SHUXING_MAP = {
    "冷凝": WAVES_FREEZING,
    "热熔": WAVES_MOLTEN,
    "导电": WAVES_VOID,
    "气动": WAVES_SIERRA,
    "衍射": WAVES_CELESTIAL,
    "湮灭": WAVES_SINKING,
}

CHAIN_COLOR = {
    0: WAVES_MOONLIT,
    1: WAVES_LINGERING,
    2: WAVES_FREEZING,
    3: WAVES_SIERRA,
    4: WAVES_VOID,
    5: AMBER,
    6: WAVES_MOLTEN,
}

CHAIN_COLOR_LIST = [CHAIN_COLOR[i] for i in range(7)]

WEAPON_RESONLEVEL_COLOR = {
    0: WAVES_MOONLIT,
    1: WAVES_LINGERING,
    2: WAVES_FREEZING,
    3: WAVES_SIERRA,
    4: WAVES_VOID,
    5: AMBER,
    6: WAVES_MOLTEN,
}


_asset_copy_lock = threading.Lock()


@lru_cache(maxsize=1024)
def _load_asset_cached(path_str: str, mtime_ns: int, mode: str) -> Image.Image:
    return Image.open(path_str).convert(mode)


def load_asset(path, mode: str = "RGBA") -> Image.Image:
    """读取素材并缓存解码结果, 返回副本(可安全修改)。文件变更(mtime)时自动失效。

    仅用于小尺寸素材(图标/背景条/模板); 大图(角色立绘/分享背景)请勿使用, 避免内存膨胀。
    """
    path_str = str(path)
    try:
        mtime_ns = os.stat(path_str).st_mtime_ns
    except OSError:
        # 文件不存在时保持与 Image.open 一致的报错行为
        return Image.open(path_str).convert(mode)

    if WutheringWavesConfig.get_config("ResourceCache").data:
        with _asset_copy_lock:
            return _load_asset_cached(path_str, mtime_ns, mode).copy()
    else:
        return Image.open(path_str).convert(mode)


def get_ICON():
    return Image.open(ICON)


async def get_random_share_bg():
    path = random.choice(os.listdir(f"{SHARE_BG_PATH}"))
    return Image.open(f"{SHARE_BG_PATH}/{path}").convert("RGBA").resize((2560, 1440))


async def get_random_share_bg_path():
    path = random.choice(os.listdir(f"{SHARE_BG_PATH}"))
    return SHARE_BG_PATH / path


async def get_random_waves_role_pile(char_id: str | None = None):
    if char_id:
        return await get_role_pile_old(char_id, custom=True)

    path = random.choice(os.listdir(f"{ROLE_PILE_PATH}"))
    return Image.open(f"{ROLE_PILE_PATH}/{path}").convert("RGBA")


def get_role_pile_path(resource_id: int | str, custom: bool = False) -> tuple[bool, Path]:
    if custom:
        custom_dir = Path(CUSTOM_CARD_PATH) / str(resource_id)
        if custom_dir.is_dir():
            paths = [path for path in custom_dir.iterdir() if path.is_file()]
            if paths:
                return True, random.choice(paths)

    path = ROLE_PILE_PATH / f"role_pile_{resource_id}.png"
    if path.exists():
        return False, path
    return False, TEXT_PATH / "缺失.png"


def get_role_pile_sync(resource_id: int | str, custom: bool = False) -> tuple[bool, Image.Image]:
    is_custom, path = get_role_pile_path(resource_id, custom)
    return is_custom, load_asset(path)


async def get_role_pile(resource_id: int | str, custom: bool = False) -> tuple[bool, Image.Image]:
    return get_role_pile_sync(resource_id, custom)


async def get_role_pile_old(resource_id: int | str, custom: bool = False) -> Image.Image:
    if custom:
        custom_dir = f"{CUSTOM_MR_CARD_PATH}/{resource_id}"
        if os.path.isdir(custom_dir) and len(os.listdir(custom_dir)) > 0:
            # logger.info(f'使用自定义角色头像: {resource_id}')
            path = random.choice(os.listdir(custom_dir))
            if path:
                return load_asset(f"{custom_dir}/{path}")

    name = f"role_pile_{resource_id}.png"
    path = ROLE_PILE_PATH / name
    if path.exists():
        return load_asset(path)
    else:
        return load_asset(TEXT_PATH / "缺失.png")


def get_square_avatar_sync(resource_id: int | str) -> Image.Image:
    path = AVATAR_PATH / f"role_head_{resource_id}.png"
    return load_asset(path if path.exists() else TEXT_PATH / "缺失.png")


async def get_square_avatar(resource_id: int | str) -> Image.Image:
    return get_square_avatar_sync(resource_id)


async def cropped_square_avatar(item_icon: Image.Image, size: int) -> Image.Image:
    # 目标尺寸
    target_width, target_height = size, size
    # 原始尺寸
    original_width, original_height = item_icon.size

    width_ratio = target_width / original_width
    height_ratio = target_height / original_height
    scale_ratio = max(width_ratio, height_ratio)
    new_width = int(original_width * scale_ratio)
    new_height = int(original_height * scale_ratio)
    resized_image = item_icon.resize((new_width, new_height), Image.Resampling.LANCZOS)
    x_center = new_width // 2
    y_center = new_height // 2
    crop_area = (
        x_center - target_width // 2,
        y_center - target_height // 2,
        x_center + target_width // 2,
        y_center + target_height // 2,
    )
    resized_image = resized_image.crop(crop_area).convert("RGBA")
    return resized_image


def get_square_weapon_sync(resource_id: int | str) -> Image.Image:
    path = WEAPON_PATH / f"weapon_{resource_id}.png"
    return load_asset(path if path.exists() else TEXT_PATH / "缺失.png")


async def get_square_weapon(resource_id: int | str) -> Image.Image:
    return get_square_weapon_sync(resource_id)


def get_attribute_sync(name: str = "", is_simple: bool = False) -> Image.Image:
    if is_simple:
        name = f"attribute/attr_simple_{name}.png"
    else:
        name = f"attribute/attr_{name}.png"
    return load_asset(TEXT_PATH / name)


async def get_attribute(name: str = "", is_simple: bool = False) -> Image.Image:
    return get_attribute_sync(name, is_simple)


def get_attribute_prop_sync(name: str = "") -> Image.Image:
    return load_asset(TEXT_PATH / f"attribute_prop/attr_prop_{name}.png")


async def get_attribute_prop(name: str = "") -> Image.Image:
    return get_attribute_prop_sync(name)


def get_attribute_effect_sync(name: str = "") -> Image.Image:
    path = TEXT_PATH / f"attribute_effect/attr_{name}.png"
    return load_asset(path if path.exists() else TEXT_PATH / "缺失.png")


async def get_attribute_effect(name: str = "") -> Image.Image:
    return get_attribute_effect_sync(name)


def get_weapon_type_sync(name: str = "") -> Image.Image:
    return load_asset(TEXT_PATH / f"weapon_type/weapon_type_{name}.png")


async def get_weapon_type(name: str = "") -> Image.Image:
    return get_weapon_type_sync(name)


def get_waves_bg(w: int, h: int, bg: str = "bg") -> Image.Image:
    img = load_asset(TEXT_PATH / f"{bg}.jpg")
    return crop_center_img(img, w, h)


def get_crop_waves_bg(w: int, h: int, bg: str = "bg") -> Image.Image:
    img = load_asset(TEXT_PATH / f"{bg}.jpg")

    width, height = img.size

    crop_box = (0, height // 2, width, height)

    cropped_image = img.crop(crop_box)

    return crop_center_img(cropped_image, w, h)


def _normalize_discord_avatar_hash(raw: str) -> str:
    """去掉 CDN 路径里可能带上的 .png / ?size= 等后缀。"""
    h = raw.split("?")[0].strip()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        if h.lower().endswith(ext):
            h = h[: -len(ext)]
            break
    return h


def _looks_like_discord_user_id(qid: str) -> bool:
    """Discord 雪花一般为 ≥17 位数字；勿与较短 QQ 号混用。"""
    return qid.isdigit() and len(qid) >= 17


def _discord_default_avatar_url(user_id: str) -> str:
    """未自定义头像时的 Discord 默认纯色头（Clyde）。"""
    idx = (int(user_id) >> 22) % 6
    return f"https://cdn.discordapp.com/embed/avatars/{idx}.png"


def _discord_custom_avatar_url(user_id: str, avatar_hash: str, size: int) -> str:
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size={size}"


def _is_usable_discord_avatar_hash(avatar_hash: str) -> bool:
    h = (avatar_hash or "").strip()
    return bool(h) and h not in {"", "None", "error", "default"} and not h.isdigit()


def _parse_discord_rank_user_id(qid: str) -> tuple[str, str] | None:
    """排行库中的 Discord user_id 形如 `雪花ID/头像hash`（hash 为十六进制，非纯数字）。"""
    if "/" not in qid:
        return None
    left, right = qid.split("/", 1)
    right = _normalize_discord_avatar_hash(right)
    if not left.isdigit() or not right:
        return None
    # QQ 官方多为 appid/openid（后段常为纯数字）；Discord hash 含 a-f
    if right.isdigit():
        return None
    if all(c in "0123456789abcdefABCDEF" for c in right):
        return left, right
    return None


def _discord_snowflake_from_rank_qid(qid: str) -> str | None:
    """从排行 user_id 提取 Discord 雪花 ID（含 `雪花/` 空 hash 上传格式）。"""
    if "/" in qid:
        left, _ = qid.split("/", 1)
        if _looks_like_discord_user_id(left):
            return left
    if _looks_like_discord_user_id(qid):
        return qid
    return None


def _rank_qid_custom_hash(qid: str) -> str:
    discord_rank = _parse_discord_rank_user_id(qid)
    if discord_rank:
        return discord_rank[1]
    if "/" in qid:
        right = _normalize_discord_avatar_hash(qid.split("/", 1)[1])
        if _is_usable_discord_avatar_hash(right):
            return right
    return ""


def _extract_discord_avatar_hash_from_url(user_id: str, avatar_url: str) -> str:
    """从 sender.avatar URL 提取自定义 hash；默认 embed 头返回空串。"""
    if not avatar_url:
        return ""
    if "/embed/avatars/" in avatar_url:
        return ""
    parts = avatar_url.split("/")
    try:
        index = parts.index(str(user_id))
        return _normalize_discord_avatar_hash(parts[index + 1])
    except (ValueError, IndexError):
        # 兜底：.../avatars/<uid>/<hash>.png
        if "/avatars/" in avatar_url:
            after = avatar_url.split("/avatars/", 1)[1]
            segs = after.split("/")
            if len(segs) >= 2 and segs[0] == str(user_id):
                return _normalize_discord_avatar_hash(segs[1])
        return ""


async def sync_non_onebot_user_avatar(ev: Event):
    """从事件中提取头像 avatar_hash 并自动更新数据库中的 hash 映射"""
    avatar_hash = "error"
    if ev.bot_id == "discord":
        # 无自定义头像时 Discord 常给 embed/avatars 或空；存空串，拉取时用默认纯色头
        avatar_hash = _extract_discord_avatar_hash_from_url(
            str(ev.user_id),
            str(ev.sender.get("avatar") or ""),
        )
    elif ev.bot_id in ["qqgroup", "qq_official"]:
        avatar_hash = ev.bot_self_id

    data = await WavesUserAvatar.select_data(ev.user_id, ev.bot_id)
    old_avatar_hash = data.avatar_hash if data else ""

    if avatar_hash != old_avatar_hash:
        await WavesUserAvatar.insert_data(user_id=ev.user_id, bot_id=ev.bot_id, avatar_hash=avatar_hash)


async def get_user_avatar(
    qid: int | str | None = None,
    avatar_url: str | None = None,
    size: int = 640,
    *,
    allow_discord_default: bool = True,
) -> Image.Image:
    qid = str(qid)
    logger.debug(f"[鸣潮] 获取头像: {qid} {avatar_url} {size}")
    urls: list[str] = []
    if avatar_url:
        urls.append(avatar_url)

    if qid:
        discord_rank = _parse_discord_rank_user_id(qid)
        snowflake = _discord_snowflake_from_rank_qid(qid)
        if discord_rank:
            lookup_id = discord_rank[0]
            custom_hash = discord_rank[1]
        elif snowflake:
            lookup_id = snowflake
            custom_hash = _rank_qid_custom_hash(qid)
        else:
            lookup_id = qid
            custom_hash = ""
        is_discord = discord_rank is not None or snowflake is not None

        data = await WavesUserAvatar.select_data(lookup_id)
        if data:  # 说明本地有个人数据，没有是排行数据
            if data.bot_id in ["qqgroup", "qq_official"]:
                appid = data.avatar_hash
                urls.append(f"http://q.qlogo.cn/qqapp/{appid}/{lookup_id}/{size}")
            elif data.bot_id in ["discord"]:
                is_discord = True
                stored = _normalize_discord_avatar_hash(data.avatar_hash or "")
                if _is_usable_discord_avatar_hash(stored):
                    custom_hash = stored

        if is_discord:
            # Discord：自定义头 → 失败再用默认纯色头；绝不走 QQ（否则雪花 ID 会出企鹅）
            if _is_usable_discord_avatar_hash(custom_hash):
                urls.append(_discord_custom_avatar_url(lookup_id, custom_hash, size))
            if allow_discord_default:
                urls.append(_discord_default_avatar_url(lookup_id))
        elif not urls:
            if qid.isdigit():
                urls.append(f"http://q1.qlogo.cn/g?b=qq&nk={qid}&s={size}")
            elif "/" in qid and qid.split("/")[0].isdigit():  # qq官方bot appid/openid
                urls.append(f"http://q.qlogo.cn/qqapp/{qid}/{size}")

    # 去重且保序
    seen: set[str] = set()
    ordered_urls = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            ordered_urls.append(u)

    last_err: Exception | None = None
    for url in ordered_urls:
        try:
            char_pic = Image.open(BytesIO((await sget(url)).content)).convert("RGBA")
            return char_pic
        except Exception as e:
            last_err = e
            logger.debug(f"[鸣潮] 头像拉取失败 {url}: {e}")

    raise ValueError(f"无法获取用户头像: {qid}") from last_err


async def rank_user_has_custom_avatar(qid: int | str | None) -> bool:
    """排行用：Discord 无自定义头像时返回 False（应改用角色头）；其它平台仍尝试用户头像。"""
    if not qid:
        return False
    qid = str(qid)
    snowflake = _discord_snowflake_from_rank_qid(qid)
    if not snowflake:
        return True

    custom_hash = _rank_qid_custom_hash(qid)
    data = await WavesUserAvatar.select_data(snowflake)
    if data and data.bot_id == "discord":
        stored = _normalize_discord_avatar_hash(data.avatar_hash or "")
        if _is_usable_discord_avatar_hash(stored):
            return True

    return _is_usable_discord_avatar_hash(custom_hash)


def _alpha_centroid(mask: Image.Image) -> tuple[float, float]:
    """遮罩不透明区域重心（用于圆形头像对齐）。"""
    alpha = mask.getchannel("A") if "A" in mask.getbands() else mask.convert("L")
    w, h = alpha.size
    px = alpha.load()
    sum_x = sum_y = total = 0
    for y in range(h):
        for x in range(w):
            a = px[x, y]
            if a > 128:
                sum_x += x * a
                sum_y += y * a
                total += a
    if not total:
        return w / 2, h / 2
    return sum_x / total, sum_y / total


def compose_rank_user_avatar(
    pic: Image.Image,
    avatar_mask: Image.Image,
    *,
    canvas_size: int = 180,
    avatar_size: int = 120,
) -> Image.Image:
    """排行圆形用户头像：把头像中心对齐遮罩 alpha 圆心，避免素材偏心导致 Discord 默认头「往右歪」。"""
    pic_temp = crop_center_img(pic, avatar_size, avatar_size)
    mask_pic = avatar_mask.copy().resize((avatar_size, avatar_size))
    cx, cy = _alpha_centroid(mask_pic)
    # paste(im, box, mask) 时图与遮罩同源坐标，只改 box 无法相对对齐；先平移头像再套遮罩
    aligned = Image.new("RGBA", (avatar_size, avatar_size))
    aligned.paste(
        pic_temp,
        (int(round(cx - avatar_size / 2)), int(round(cy - avatar_size / 2))),
    )
    img = Image.new("RGBA", (canvas_size, canvas_size))
    # 保留原先 (0, -5) 在条上的大致位置
    img.paste(aligned, (0, -5), mask_pic)
    return img


async def get_event_avatar(
    ev: Event,
    avatar_path: Path | None = None,
    size: int = 640,
    is_valid_at_param: bool = True,
) -> Image.Image:
    img = None

    if is_valid_at_param:
        from ..utils.at_help import is_valid_at

        is_valid_at_param = is_valid_at(ev)

    # 尝试获取@用户的头像
    if ev.at and is_valid_at_param:
        try:
            img = await get_user_avatar(qid=ev.at, size=size)
        except Exception:
            img = None

    # 尝试获取使用者头像
    if img is None:
        try:
            img = await get_user_avatar(qid=ev.user_id, size=size)
        except Exception:
            img = None

    if img is None and "avatar" in ev.sender and ev.sender["avatar"]:  # qqgroup不返回avatar...
        avatar_url: str = ev.sender["avatar"]
        if avatar_url.startswith(("http", "https")):
            try:
                content = (await sget(avatar_url)).content
                img = Image.open(BytesIO(content)).convert("RGBA")
            except Exception:
                img = None

    if img is None and avatar_path:
        pic_path_list = list(avatar_path.iterdir())
        if pic_path_list:
            path = random.choice(pic_path_list)
            img = Image.open(path).convert("RGBA")

    if img is None:
        img = await get_square_avatar(1203)

    return img


def get_small_logo(logo_num=1):
    return load_asset(TEXT_PATH / f"logo_small_{logo_num}.png")


def get_footer(color: Literal["white", "black", "encore"] = "white"):
    return load_asset(TEXT_PATH / f"footer_{color}.png")


def add_footer(
    img: Image.Image,
    w: int = 0,
    offset_y: int = 0,
    is_invert: bool = False,
    color: Literal["white", "black", "encore"] = "white",
):
    footer = get_footer(color)
    if is_invert:
        r, g, b, a = footer.split()
        rgb_image = Image.merge("RGB", (r, g, b))
        rgb_image = ImageOps.invert(rgb_image.convert("RGB"))
        r2, g2, b2 = rgb_image.split()
        footer = Image.merge("RGBA", (r2, g2, b2, a))

    if w != 0:
        footer = footer.resize(
            (w, int(footer.size[1] * w / footer.size[0])),
        )

    x, y = (
        int((img.size[0] - footer.size[0]) / 2),
        img.size[1] - footer.size[1] - 20 + offset_y,
    )

    img.paste(footer, (x, y), footer)
    return img


def change_color_sync(
    chain,
    color: tuple = (255, 255, 255),
    w: int | None = None,
    h: int | None = None,
):
    if w is None:
        w = chain.size[0]
    if h is None:
        h = chain.size[1]

    if not isinstance(h, int) or not isinstance(w, int):
        return chain

    # 等价于逐像素将 RGB 替换为纯色并保留 alpha, C 层实现
    region = chain.crop((0, 0, w, h))
    solid = Image.new("RGBA", region.size, color + (0,))
    solid.putalpha(region.getchannel("A"))
    chain.paste(solid, (0, 0))

    return chain


async def change_color(
    chain,
    color: tuple = (255, 255, 255),
    w: int | None = None,
    h: int | None = None,
):
    return change_color_sync(chain, color, w, h)


def draw_text_with_shadow(
    image: ImageDraw.ImageDraw,
    text: str,
    _x: int,
    _y: int,
    font: ImageFont.FreeTypeFont,
    fill_color: str = "white",
    shadow_color: float | tuple[int, ...] | str = "black",
    offset: tuple[int, int] = (2, 2),
    anchor="rm",
):
    """描边"""
    for i in range(-offset[0], offset[0] + 1):
        for j in range(-offset[1], offset[1] + 1):
            image.text((_x + i, _y + j), text, font=font, fill=shadow_color, anchor=anchor)

    image.text((_x, _y), text, font=font, fill=fill_color, anchor=anchor)
    image.text((_x, _y), text, font=font, fill=fill_color, anchor=anchor)


def compress_to_webp(image_path: Path, quality: int = 80, delete_original: bool = False) -> tuple[bool, Path]:
    try:
        from PIL import Image

        # 确保文件存在
        if not image_path.exists():
            logger.warning(f"图片不存在: {image_path}")
            return False, image_path

        # 检查文件是否已经是webp格式
        if image_path.suffix.lower() == ".webp":
            logger.info(f"图片已经是webp格式: {image_path}")
            return False, image_path

        # 创建webp文件路径
        webp_path = image_path.with_suffix(".webp")

        # 打开图片
        img = Image.open(image_path)

        # 记录原始大小
        orig_size = image_path.stat().st_size

        # 保存为webp格式
        img.save(webp_path, "WEBP", quality=quality, method=6)

        # 计算压缩率
        webp_size = webp_path.stat().st_size
        compression_ratio = (1 - webp_size / orig_size) * 100 if orig_size > 0 else 0
        logger.info(f"图片 {image_path.name} 压缩为webp格式, 压缩率: {compression_ratio:.2f}%")

        # 删除原图片（如果需要）
        if delete_original:
            image_path.unlink()
            logger.info(f"原图片已删除: {image_path}")

        return True, webp_path

    except Exception as e:
        logger.error(f"压缩图片为webp格式失败: {e}")
        return False, image_path


async def draw_avatar_with_star(
    avatar: Image.Image,
    star_level: int = 5,
    need_text: bool = True,
    img_color: float | tuple[float, ...] | str | None = (0, 0, 0, 255),
    item_width: int = 144,
    item_height: int = 170,
) -> Image.Image:
    if need_text:
        img = Image.new("RGBA", (item_width, item_height), img_color)
    else:
        img = Image.new("RGBA", (item_width, item_width), img_color)

    # 144*144
    star_bg = load_asset(TEXT_PATH / f"star_{star_level}.png")
    avatar = avatar.resize((item_width, item_width))

    img.alpha_composite(avatar, (0, 0))
    img.alpha_composite(star_bg, (0, 0))
    return img


async def get_star_bg(star_level: int = 5) -> Image.Image:
    return load_asset(TEXT_PATH / f"star_{star_level}.png")


async def pic_download_from_url(
    path: Path,
    pic_url: str,
) -> Image.Image:
    path.mkdir(parents=True, exist_ok=True)

    name = pic_url.split("/")[-1]
    _path = path / name
    if not _path.exists():
        from gsuid_core.utils.download_resource.download_file import download

        await download(pic_url, path, name, tag="[鸣潮]")

    try:
        return Image.open(_path).convert("RGBA")
    except Exception:
        return Image.open(TEXT_PATH / "缺失.png").convert("RGBA")


async def get_custom_gaussian_blur(img: Image.Image) -> Image.Image:
    from ..wutheringwaves_config.wutheringwaves_config import ShowConfig

    radius = ShowConfig.get_config("BlurRadius").data
    if radius > 0:
        # 应用高斯模糊
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))
        # 调整亮度和对比度
        brightness = ShowConfig.get_config("BlurBrightness").data
        try:
            brightness = float(brightness)
        except Exception:
            brightness = 1
        contrast = ShowConfig.get_config("BlurContrast").data
        try:
            contrast = float(contrast)
        except Exception:
            contrast = 1

        img = ImageEnhance.Brightness(img).enhance(brightness)
        # 调整对比度
        img = ImageEnhance.Contrast(img).enhance(contrast)
    return img
