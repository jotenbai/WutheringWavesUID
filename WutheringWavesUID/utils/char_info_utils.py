from collections.abc import Generator
import json
from typing import Any

import aiofiles
from gsuid_core.logger import logger
from gsuid_core.models import Event
import httpx

from ..utils.api.model import RoleDetailData
from ..utils.api.wwapi import GET_ROLE_DETAIL_URL, RoleDetailResponse
from ..wutheringwaves_config.wutheringwaves_config import WutheringWavesConfig
from .resource.RESOURCE_PATH import PLAYER_PATH


async def get_all_role_detail_info_list(
    uid: str,
) -> Generator[RoleDetailData, Any, None] | None:
    path = PLAYER_PATH / uid / "rawData.json"
    if not path.exists():
        return None
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            player_data = json.loads(await f.read())
    except Exception as e:
        logger.exception(f"get role detail info failed {path}:", e)
        path.unlink(missing_ok=True)
        return None

    return iter(RoleDetailData(**r) for r in player_data)


async def get_all_role_detail_info(uid: str) -> dict[str, RoleDetailData] | None:
    _all = await get_all_role_detail_info_list(uid)
    if not _all:
        return None
    return {r.role.roleName: r for r in _all}


async def get_all_roleid_detail_info(
    uid: str,
) -> dict[str, RoleDetailData] | None:
    _all = await get_all_role_detail_info_list(uid)
    if not _all:
        return None
    return {str(r.role.roleId): r for r in _all}


async def get_all_roleid_detail_info_int(
    uid: str,
) -> dict[int, RoleDetailData] | None:
    _all = await get_all_role_detail_info_list(uid)
    if not _all:
        return None
    return {r.role.roleId: r for r in _all}


async def get_role_detail_online(waves_id: str | int) -> RoleDetailResponse | None:
    WavesToken = WutheringWavesConfig.get_config("WavesToken").data

    if not WavesToken:
        return

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(
                GET_ROLE_DETAIL_URL,
                json={"waves_id": str(waves_id)},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {WavesToken}",
                },
                timeout=httpx.Timeout(10),
            )
            # logger.debug(f"获取角色细节: {res.text}")
            if res.status_code == 200:
                return RoleDetailResponse.model_validate(res.json())
        except Exception as e:
            logger.exception(f"获取角色细节失败: {e}")


async def get_roleid_detail_online(
    uid: str,
) -> dict[str, RoleDetailData] | None:
    result = await get_role_detail_online(uid)
    if not result or not result.data.data:
        return None
    _data = [RoleDetailData(**r) for r in result.data.data]
    return {str(r.role.roleId): r for r in _data}


async def get_role_detail_info_with_refresh(
    ev: Event,
    user_id: str,
    uid: str,
    needed_role_ids: list[str | int],
) -> dict[str, RoleDetailData] | None:
    """获取角色详情，对本地缺失的角色自动刷新单角色面板数据。

    先从本地数据库读取 role_detail_info_map，若 needed_role_ids 中有角色
    在本地缺失，则调用 draw_refresh_char_detail_img(need_boolean=True)
    刷新缺失角色，刷新成功后重新读取本地数据。

    Args:
        ev: Event 实例
        user_id: 用户ID
        uid: 鸣潮UID
        needed_role_ids: 需要的角色ID列表

    Returns:
        角色详细信息映射 {roleId_str: RoleDetailData}，可能为 None
    """
    role_detail_info_map = await get_all_roleid_detail_info(uid)

    needed_ids = [str(rid) for rid in needed_role_ids]

    if role_detail_info_map:
        missing_ids = [rid for rid in needed_ids if rid not in role_detail_info_map]
    else:
        missing_ids = needed_ids

    if not missing_ids:
        return role_detail_info_map

    # 懒加载避免循环导入；bot 参数未实际使用，传 None
    from ..wutheringwaves_charinfo.draw_refresh_char_card import draw_refresh_char_detail_img

    try:
        result = await draw_refresh_char_detail_img(
            bot=None,  # type: ignore[arg-type]
            ev=ev,
            user_id=user_id,
            uid=uid,
            buttons=[],
            refresh_type=missing_ids,
            need_boolean=True,
        )
        # 刷新成功（返回 True）后重新获取本地数据
        if result is True:
            role_detail_info_map = await get_all_roleid_detail_info(uid)
        else:
            logger.debug(f"[角色获取更新] 刷新缺失角色未更新或失败: {result}")
    except Exception as e:
        logger.warning(f"[角色获取更新] 刷新缺失角色异常: {e}")

    return role_detail_info_map
