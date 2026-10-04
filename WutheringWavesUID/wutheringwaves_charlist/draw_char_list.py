from pathlib import Path

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img
from PIL import Image, ImageDraw

from ..utils.api.model import RoleDetailData, WeaponData
from ..utils.ascension.weapon import get_breach
from ..utils.char_info_utils import get_all_roleid_detail_info_int
from ..utils.database.models import WavesBind
from ..utils.error_reply import WAVES_CODE_099
from ..utils.expression_ctx import WavesCharRank, format_energy_regen_line, get_waves_char_rank
from ..utils.fonts.waves_fonts import (
    waves_font_16,
    waves_font_18,
    waves_font_20,
    waves_font_22,
    waves_font_24,
    waves_font_25,
    waves_font_26,
    waves_font_30,
    waves_font_38,
    waves_font_40,
    waves_font_42,
)
from ..utils.hint import error_reply
from ..utils.zh_convert import TradRaw
from ..utils.image import (
    CHAIN_COLOR,
    CHAIN_COLOR_LIST,
    GOLD,
    GREY,
    SPECIAL_GOLD,
    WEAPON_RESONLEVEL_COLOR,
    add_footer,
    compose_ring_avatar,
    get_attribute,
    get_event_avatar,
    get_waves_id_owner_avatar,
    get_square_avatar,
    get_square_weapon,
    get_waves_bg,
)
from ..utils.refresh_char_detail import refresh_char
from ..utils.resource.constant import NORMAL_LIST
from ..utils.resource.download_file import get_skill_img
from ..utils.util import send_master_info
from ..utils.waves_api import waves_api
from ..wutheringwaves_analyzecard.user_info_utils import get_user_detail_info
from ..wutheringwaves_config import WutheringWavesConfig
from ..wutheringwaves_grouprank.models import GroupRankRecord

TEXT_PATH = Path(__file__).parent / "texture2d"

# 未满5件声骸角色的头像网格：左右与详情行对齐（头像可见左缘 66 ~ 底框右缘 931），
# 等宽 10 列，横纵同一 gap；头像裁掉透明边（draw_pic 可见区 101x93）后等比填满格子
BRIEF_COLS = 10
BRIEF_LEFT = 66
BRIEF_RIGHT = 931
BRIEF_GAP = 8
BRIEF_AVATAR_BOX = (6, 6, 107, 99)
BRIEF_CELL_W = (BRIEF_RIGHT - BRIEF_LEFT - (BRIEF_COLS - 1) * BRIEF_GAP) / BRIEF_COLS
BRIEF_CELL_H = BRIEF_CELL_W * (BRIEF_AVATAR_BOX[3] - BRIEF_AVATAR_BOX[1]) / (BRIEF_AVATAR_BOX[2] - BRIEF_AVATAR_BOX[0])
BRIEF_TITLE_H = 50


def get_equipped_phantom_num(role_detail: RoleDetailData) -> int:
    phantom_data = role_detail.phantomData
    if not phantom_data or not phantom_data.equipPhantomList:
        return 0
    return sum(1 for p in phantom_data.equipPhantomList if p)


async def save_train_data_to_db(
    user_id: str,
    waves_id: str,
    name: str,
    waves_char_rank: list,
) -> bool:
    """保存练度数据到数据库"""
    try:
        total_score = sum(c.score for c in waves_char_rank if c.score and c.score >= 175)
        char_scores = [{"role_id": c.roleId, "score": c.score} for c in waves_char_rank if c.score and c.score >= 175]

        await GroupRankRecord.save_train_record(
            user_id=user_id,
            waves_id=waves_id,
            name=name,
            train_score=total_score,
            char_scores=char_scores,
        )
        logger.debug(
            f"[练度排行] 用户{user_id} 的UID {waves_id} 练度数据保存到数据库成功, 总分 {total_score}，角色分数 {char_scores}"
        )
        return True
    except Exception as e:
        logger.warning(f"[练度排行] 用户{user_id} 的UID {waves_id} 练度数据保存到数据库失败: {e}")
        await send_master_info(f"[练度排行] 用户{user_id} 的UID {waves_id} 练度数据保存到数据库失败: {e}")
        return False


async def get_all_roleid_detail_info(
    ev: Event,
    uid: str,
    user_id: str,
    ck: str,
    is_refresh: bool = False,
    is_peek: bool = False,
):
    if not WutheringWavesConfig.get_config("RoleListQuery").data:
        all_role_detail = await get_all_roleid_detail_info_int(uid)
        if all_role_detail:
            return all_role_detail
    else:
        # 根据面板数据获取详细信息
        if is_refresh or is_peek:
            await refresh_char(ev, uid, user_id, ck)
        all_role_detail = await get_all_roleid_detail_info_int(uid)
        if all_role_detail:
            return all_role_detail

        if is_refresh or is_peek:
            # 已经刷新过，但是没有获取到数据
            return None

        # 尝试刷新
        await refresh_char(ev, uid, user_id, ck)
        all_role_detail = await get_all_roleid_detail_info_int(uid)
        if all_role_detail:
            return all_role_detail


async def draw_char_list_img(
    uid: str,
    ev: Event,
    user_id: str,
    is_refresh: bool = False,
    is_peek: bool = False,
    user_waves_id: str = "",
) -> str | bytes:
    _, ck = await waves_api.get_ck_result(user_waves_id, user_id, ev.bot_id)
    account_info = await get_user_detail_info(uid)

    all_role_detail = await get_all_roleid_detail_info(
        ev,
        uid,
        user_id,
        ck,
        is_refresh,
        is_peek,
    )
    if not all_role_detail:
        if waves_api.is_net(uid):
            return error_reply(WAVES_CODE_099)
        if waves_api.last_error:
            return waves_api.last_error
        return error_reply(code=-111, msg="练度获取失败，请先刷新角色面板")

    waves_char_rank = await get_waves_char_rank(uid, all_role_detail)
    waves_char_rank.sort(key=lambda i: (i.score, i.starLevel, i.level, i.chain, i.roleId), reverse=True)

    # 保存练度数据到数据库；按特征码查看他人时记在机主名下，查不到唯一机主则不写
    save_user_id = user_id
    if is_peek and uid != user_waves_id:
        save_user_id = await WavesBind.get_uid_owner_user_id(uid, ev.bot_id)
    if save_user_id:
        await save_train_data_to_db(
            user_id=save_user_id, waves_id=uid, name=account_info.name, waves_char_rank=waves_char_rank
        )

    # 统计数据
    # up角色
    up_num = 0
    # 高练角色
    level_num = 0
    # 高链角色
    chain_num = 0
    # 高链五星角色
    chain_num_5 = 0
    # 所有角色
    all_num = 0
    # 五星角色数量
    all_num_5 = 0

    for _, rank in enumerate(waves_char_rank):
        rank: WavesCharRank
        role_detail = all_role_detail[rank.roleId]
        if rank.starLevel == 5 and rank.roleName not in NORMAL_LIST:
            up_num += 1

        if rank.score >= 175 and rank.score_bg in ["s", "ss", "sss"]:
            level_num += 1

        if role_detail.get_chain_num() == 6:
            if rank.starLevel == 5:
                chain_num_5 += 1
            else:
                chain_num += 1

        all_num += 1
        if rank.starLevel == 5:
            all_num_5 += 1

    # 五件声骸都佩戴才展示详情行，其余只在末尾列头像
    render_list = []
    brief_list = []
    for _rank in waves_char_rank:
        if get_equipped_phantom_num(all_role_detail[_rank.roleId]) >= 5:
            render_list.append(_rank)
        else:
            brief_list.append(_rank)

    avatar_h = 230
    info_bg_h = 260
    bar_star_h = 110
    brief_h = 0
    if brief_list:
        brief_rows = (len(brief_list) + BRIEF_COLS - 1) // BRIEF_COLS
        brief_h = BRIEF_TITLE_H + round(brief_rows * BRIEF_CELL_H + (brief_rows - 1) * BRIEF_GAP) + 30
    h = avatar_h + info_bg_h + len(render_list) * bar_star_h + brief_h + 80
    card_img = get_waves_bg(1000, h, "bg3")

    # 基础信息 名字 特征码
    base_info_bg = Image.open(TEXT_PATH / "base_info_bg.png")
    base_info_draw = ImageDraw.Draw(base_info_bg)
    base_info_draw.text((275, 120), TradRaw(account_info.name[:7]), "white", waves_font_30, "lm")
    base_info_draw.text((226, 173), f"特征码:  {account_info.id}", GOLD, waves_font_25, "lm")
    card_img.paste(base_info_bg, (15, 20), base_info_bg)

    # 头像 头像环
    avatar = await draw_pic_with_ring(ev, is_peek, uid)
    avatar_ring = Image.open(TEXT_PATH / "avatar_ring.png")
    card_img.paste(avatar, (25, 70), avatar)
    avatar_ring = avatar_ring.resize((180, 180))
    card_img.paste(avatar_ring, (35, 80), avatar_ring)

    # 账号基本信息，由于可能会没有，放在一起
    if account_info.is_full:
        title_bar = Image.open(TEXT_PATH / "title_bar.png")
        title_bar_draw = ImageDraw.Draw(title_bar)
        title_bar_draw.text((660, 125), "账号等级", GREY, waves_font_26, "mm")
        title_bar_draw.text((660, 78), f"Lv.{account_info.level}", "white", waves_font_42, "mm")

        title_bar_draw.text((810, 125), "世界等级", GREY, waves_font_26, "mm")
        title_bar_draw.text((810, 78), f"Lv.{account_info.worldLevel}", "white", waves_font_42, "mm")
        card_img.paste(title_bar, (-20, 70), title_bar)

    for index, _rank in enumerate(render_list):
        _rank: WavesCharRank
        role_detail: RoleDetailData = all_role_detail[_rank.roleId]
        bar_star = Image.open(TEXT_PATH / f"bar_{_rank.starLevel}star.png")
        bar_star_draw = ImageDraw.Draw(bar_star)
        role_avatar = await draw_pic(role_detail.role.roleId)

        bar_star.paste(role_avatar, (60, 0), role_avatar)

        role_attribute = await get_attribute(
            role_detail.role.attributeName,
            is_simple=True,  # type: ignore
        )
        role_attribute = role_attribute.resize((40, 40)).convert("RGBA")
        bar_star.alpha_composite(role_attribute, (170, 20))
        bar_star_draw.text((180, 83), f"Lv.{_rank.level}", GREY, waves_font_22, "mm")

        # 命座
        info_block = Image.new("RGBA", (40, 20), color=(255, 255, 255, 0))
        info_block_draw = ImageDraw.Draw(info_block)
        fill = CHAIN_COLOR[role_detail.get_chain_num()] + (int(0.9 * 255),)
        info_block_draw.rectangle([0, 0, 40, 20], fill=fill)
        info_block_draw.text((2, 10), f"{role_detail.get_chain_name()}", "white", waves_font_18, "lm")
        bar_star.alpha_composite(info_block, (120, 15))

        # 评分与共效（有声骸时显示）
        if _rank.score > 0.0:
            score_bg = Image.open(TEXT_PATH / f"score_{_rank.score_bg}.png")
            bar_star.alpha_composite(score_bg, (200, 2))
            bar_star_draw.text(
                (348, 42),
                f"{_rank.score:.2f}",
                "white",
                waves_font_30,
                "mm",
            )
            bar_star_draw.text(
                (348, 75),
                format_energy_regen_line(_rank.energy_regen),
                SPECIAL_GOLD,
                waves_font_16,
                "mm",
            )

        # 技能
        skill_img_temp = Image.new("RGBA", (1500, 300))
        for i, _skill in enumerate(role_detail.get_skill_list()):
            if _skill.skill.type == "延奏技能" or _skill.skill.type == "谐度破坏":
                continue
            temp = Image.new("RGBA", (120, 140))
            skill_bg = Image.open(TEXT_PATH / "skill_bg.png")
            temp.alpha_composite(skill_bg)

            skill_img = await get_skill_img(role_detail.role.roleId, _skill.skill.name, _skill.skill.iconUrl)
            skill_img = skill_img.resize((70, 70))
            # skill_img = ImageEnhance.Brightness(skill_img).enhance(0.3)
            temp.alpha_composite(skill_img, (25, 25))

            temp_draw = ImageDraw.Draw(temp)
            # temp_draw.text(
            #     (62, 45), f"{_skill.skill.type}", "white", waves_font_30, "mm"
            # )
            color = "white"
            if _skill.level == 10:
                color = CHAIN_COLOR_LIST[-1]
            elif _skill.level == 9:
                color = CHAIN_COLOR_LIST[-2]
            elif _skill.level == 8:
                color = CHAIN_COLOR_LIST[-3]
            elif _skill.level == 7:
                color = CHAIN_COLOR_LIST[-4]
            elif _skill.level == 6:
                color = CHAIN_COLOR_LIST[-5]
            temp_draw.text((62, 120), f"{_skill.level}", color, waves_font_38, "mm")

            _x = 100 + i * 65
            skill_img_temp.alpha_composite(temp.resize((70, 82)), dest=(_x, 0))
        bar_star.alpha_composite(skill_img_temp, dest=(300, 10))

        # 武器
        weapon_bg_temp = Image.new("RGBA", (600, 300))

        weaponData: WeaponData = role_detail.weaponData
        weapon_icon = await get_square_weapon(weaponData.weapon.weaponId)
        weapon_icon = crop_center_img(weapon_icon, 110, 110)
        weapon_icon_bg = get_weapon_icon_bg(weaponData.weapon.weaponStarLevel)
        weapon_icon_bg.paste(weapon_icon, (10, 20), weapon_icon)

        weapon_bg_temp_draw = ImageDraw.Draw(weapon_bg_temp)
        weapon_bg_temp_draw.text(
            (200, 30),
            f"{weaponData.weapon.weaponName}",
            SPECIAL_GOLD,
            waves_font_40,
            "lm",
        )
        weapon_bg_temp_draw.text((203, 75), f"Lv.{weaponData.level}/90", "white", waves_font_30, "lm")

        _x = 220 + 43 * len(weaponData.weapon.weaponName)
        _y = 37

        wrc_fill = WEAPON_RESONLEVEL_COLOR[weaponData.resonLevel] + (int(0.8 * 255),)  # type: ignore
        weapon_bg_temp_draw.rounded_rectangle([_x - 15, _y - 15, _x + 50, _y + 15], radius=7, fill=wrc_fill)
        weapon_bg_temp_draw.text((_x, _y), f"精{weaponData.resonLevel}", "white", waves_font_24, "lm")

        weapon_breach = get_breach(weaponData.breach, weaponData.level)
        for i in range(0, weapon_breach):  # type: ignore
            promote_icon = Image.open(TEXT_PATH / "promote_icon.png")
            weapon_bg_temp.alpha_composite(promote_icon, dest=(200 + 40 * i, 100))

        weapon_bg_temp.alpha_composite(weapon_icon_bg, dest=(45, 0))

        bar_star.alpha_composite(weapon_bg_temp.resize((260, 130)), dest=(710, 25))

        card_img.paste(bar_star, (0, avatar_h + info_bg_h + index * bar_star_h), bar_star)

    if brief_list:
        brief_y = avatar_h + info_bg_h + len(render_list) * bar_star_h + 10
        card_draw = ImageDraw.Draw(card_img)
        card_draw.text(
            ((BRIEF_LEFT + BRIEF_RIGHT) // 2, brief_y + BRIEF_TITLE_H // 2),
            "以下角色未装配5件声骸，仅显示头像",
            GREY,
            waves_font_22,
            "mm",
        )
        grid_y = brief_y + BRIEF_TITLE_H
        for index, _rank in enumerate(brief_list):
            role_detail = all_role_detail[_rank.roleId]
            tile = await draw_brief_tile(role_detail)
            col, row = index % BRIEF_COLS, index // BRIEF_COLS
            card_img.alpha_composite(
                tile,
                (
                    round(BRIEF_LEFT + col * (BRIEF_CELL_W + BRIEF_GAP)),
                    round(grid_y + row * (BRIEF_CELL_H + BRIEF_GAP)),
                ),
            )

    # 简单描述
    info_bg = Image.open(TEXT_PATH / "info_bg.png")
    info_bg_draw = ImageDraw.Draw(info_bg)
    info_bg_draw.text((240, 120), f"{up_num}/{all_num}", "white", waves_font_40, "mm")
    info_bg_draw.text((240, 160), "up角色", "white", waves_font_20, "mm")

    info_bg_draw.text((410, 120), f"{level_num}/{all_num}", "white", waves_font_40, "mm")
    info_bg_draw.text((410, 160), "高练角色", "white", waves_font_20, "mm")

    info_bg_draw.text((580, 120), f"{chain_num}/{all_num - all_num_5}", "white", waves_font_40, "mm")
    info_bg_draw.text((580, 160), "高链4星", "white", waves_font_20, "mm")

    info_bg_draw.text((750, 120), f"{chain_num_5}/{all_num_5}", "white", waves_font_40, "mm")
    info_bg_draw.text((750, 160), "高链5星", "white", waves_font_20, "mm")

    char_info = f"共 {len(waves_char_rank)} 名角色"
    info_bg_draw.text((500, 240), char_info, "white", waves_font_38, "mm")

    card_img.paste(info_bg, (0, avatar_h), info_bg)

    card_img = add_footer(card_img)
    card_img = await convert_img(card_img)
    return card_img


async def draw_pic_with_ring(ev: Event, is_peek: bool = False, waves_id: str = ""):
    if is_peek:
        pic = await get_waves_id_owner_avatar(waves_id, ev.bot_id) if waves_id else None
        if pic is None:
            pic = await get_square_avatar(1505)
    else:
        pic = await get_event_avatar(ev)

    mask_pic = Image.open(TEXT_PATH / "avatar_mask.png")
    return compose_ring_avatar(pic, mask_pic)


async def draw_pic(roleId):
    pic = await get_square_avatar(roleId)
    pic_temp = Image.new("RGBA", pic.size)
    pic_temp.paste(pic.resize((160, 160)), (10, 10))

    mask_pic = Image.open(TEXT_PATH / "avatar_mask.png")
    mask_pic_temp = Image.new("RGBA", mask_pic.size)
    mask_pic_temp.paste(mask_pic, (-20, -45), mask_pic)

    img = Image.new("RGBA", (180, 180))
    mask_pic_temp = mask_pic_temp.resize((160, 160))
    resize_pic = pic_temp.resize((160, 160))
    img.paste(resize_pic, (0, 0), mask_pic_temp)

    return img


async def draw_brief_tile(role_detail: RoleDetailData) -> Image.Image:
    """未满5件声骸角色：头像 + 右上共鸣链标签（与详情行同样的相对位置）"""
    tile = Image.new("RGBA", (130, 120))
    role_avatar = await draw_pic(role_detail.role.roleId)
    tile.alpha_composite(role_avatar.crop((0, 0, 130, 120)))

    chain_block = Image.new("RGBA", (40, 20), color=(255, 255, 255, 0))
    chain_draw = ImageDraw.Draw(chain_block)
    fill = CHAIN_COLOR[role_detail.get_chain_num()] + (int(0.9 * 255),)
    chain_draw.rectangle([0, 0, 40, 20], fill=fill)
    chain_draw.text((2, 10), f"{role_detail.get_chain_name()}", "white", waves_font_18, "lm")
    tile.alpha_composite(chain_block, (60, 15))
    tile = tile.crop(BRIEF_AVATAR_BOX)
    return tile.resize((round(BRIEF_CELL_W), round(BRIEF_CELL_H)), Image.LANCZOS)


def get_weapon_icon_bg(star: int = 3) -> Image.Image:
    if star < 3:
        star = 3
    bg_path = TEXT_PATH / f"weapon_icon_bg_{star}.png"
    bg_img = Image.open(bg_path)
    return bg_img
