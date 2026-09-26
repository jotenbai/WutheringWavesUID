"""队友增益：配置、装备目录、施加逻辑。

- 指令侧：解析「换队友」后把配队挂到 attr（``attr.set_teammate``）
- 计算侧：伤害函数在合适位置调一次 ``attr.set_teammate_buff()``
- 装备目录：合鸣 / 声骸 / 武器里能拐队友的那些都登记在下面，更新只改这一处
- 角色侧：默认用什么装备、能调什么状态，写在 register_char.py 的
  ``teammate_equip`` / ``teammate_states`` 声明里
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import functools
import inspect
from typing import Any

from .utils import (
    CHAR_ATTR_FREEZING,
    CHAR_ATTR_MOLTEN,
    CHAR_ATTR_SIERRA,
    CHAR_ATTR_SINKING,
    CHAR_ATTR_VOID,
    Sync_Strike_Role_Ids,
    cast_variation,
    phantom_damage,
    temp_atk,
)

SONATA_MARK = "合鸣效果-"
ECHO_MARK = "声骸技能-"

KIND_SONATA = "sonata"
KIND_ECHO = "echo"
KIND_WEAPON = "weapon"

KIND_LABELS = {
    KIND_SONATA: "合鸣效果",
    KIND_ECHO: "声骸技能",
    KIND_WEAPON: "专武",
}

KIND_MARKS = {
    KIND_SONATA: SONATA_MARK,
    KIND_ECHO: ECHO_MARK,
}

OFF_VALUES = {"关", "无", "不带", "none", "off", "0"}
DEFAULT_VALUES = {"默认", "default", "开", "1"}

# 条件套：顶层写默认，``cases`` 里按顺序取第一个所有条件都命中的，只覆盖它写了的键
CASES_KEY = "cases"

CASE_ENV = "env"
CASE_DAMAGE = "damage"
CASE_TEMPLATE = "template"
CASE_CHAIN = "chain"

CASE_KEYS = (CASE_ENV, CASE_DAMAGE, CASE_TEMPLATE, CASE_CHAIN)

# 走目录施加的两类；顺序固定，不能用 set（后加的先算会改浮点求和结果）
EQUIP_KINDS = (KIND_SONATA, KIND_ECHO)
# 条件套能覆盖的键：合鸣 / 声骸 / 专武
CASE_EQUIP_KEYS = (*EQUIP_KINDS, KIND_WEAPON)


@dataclass(frozen=True)
class EquipPreset:
    """一套合鸣 / 一个声骸能提供的队伍增益。

    ``apply`` 直接写对 ``DamageAttribute`` 的调用，和 ``_do_buff`` 里写法一致，
    不再用「字段名 + 数值」这种中间形态去拼方法名。

    原本写在角色代码里的生效条件（「门」）也一起搬到这里：条件不成立时
    ``apply`` 什么都不写。条件只能读 attr 上当时的状态 —— 主角色的模板 /
    属性 / 伤害类型 / 环境位，例如 ``attr.char_template == temp_atk``。
    """

    key: str
    kind: str
    msg: str
    apply: Callable[[Any, str, str], None]

    def title(self, char_name: str) -> str:
        return f"{char_name}-{KIND_MARKS[self.kind]}{self.key}"

    def run(self, attr, char_name: str) -> None:
        self.apply(attr, self.title(char_name), self.msg)


def _sonata(key: str, msg: str, apply: Callable[[Any, str, str], None]) -> EquipPreset:
    return EquipPreset(key, KIND_SONATA, msg, apply)


def _echo(key: str, msg: str, apply: Callable[[Any, str, str], None]) -> EquipPreset:
    return EquipPreset(key, KIND_ECHO, msg, apply)


def _team_has_sync_strike(attr) -> bool:
    """队伍里有没有「协同攻击」角色（高天共奏之曲那条门的触发源）。

    口径（用户确认）：只看队友，不算主C自己 —— 队友里有协同攻击角色
    （``Sync_Strike_Role_Ids``）才开门，主C自己打协同攻击不算。
    """
    ids = set(getattr(attr, "teammate_char_ids", None) or ())
    return not ids.isdisjoint(Sync_Strike_Role_Ids)


SONATA_PRESETS: dict[str, EquipPreset] = {
    p.key: p
    for p in (
        _sonata(
            "轻云出月",
            "使用延奏技能后，下一个登场的共鸣者攻击提升22.5%",
            lambda attr, title, msg: attr.add_atk_percent(0.225, title, msg) if attr.char_template == temp_atk else None,
        ),
        _sonata(
            "隐世回光",
            "全队共鸣者攻击提升15%",
            lambda attr, title, msg: attr.add_atk_percent(0.15, title, msg) if attr.char_template == temp_atk else None,
        ),
        _sonata(
            "雪落无声之愿",
            "使用延奏技能后，下一个登场的角色冷凝伤害提升25%",
            # 主C侧 damage.py 的「落雪」分支：给的是冷凝伤害加成，不是攻击
            lambda attr, title, msg: (
                attr.add_dmg_bonus(0.25, title, msg) if attr.env_glacio_chafe and attr.char_attr == CHAR_ATTR_FREEZING else None
            ),
        ),
        _sonata(
            "羽落空尘之歌",
            "获得【重明之羽】：每1%共鸣效率使队中角色攻击提升0.1%，上限25%",
            # 【重明之羽】是添加【霜渐效应】才拿到的（主C侧 damage.py 的同一个分支）
            lambda attr, title, msg: (
                attr.add_atk_percent(0.25, title, msg) if attr.char_template == temp_atk and attr.env_glacio_chafe else None
            ),
        ),
        _sonata(
            "星构寻辉之环",
            "为队中角色治疗时，使队伍中角色攻击提升25%",
            lambda attr, title, msg: attr.add_atk_percent(0.25, title, msg) if attr.char_template == temp_atk else None,
        ),
        _sonata(
            "逆光跃彩之约",
            "角色施放延奏技能后，下一个变奏技能登场的角色攻击提升15%",
            # 官方文案没有集谐条件，不用门；达妮娅 / 琳奈只是各自在这套配装下会打开集谐。
            lambda attr, title, msg: (
                (
                    attr.add_atk_percent(0.15, title, msg),
                    attr.add_atk_percent(0.15, title, "其谐度破坏增幅使攻击额外提升15%"),
                )
                if attr.char_template == temp_atk
                else None
            )
            and None,
        ),
        _sonata(
            "斑驳粉饰之沫",
            "使用延奏技能后，下一个登场的角色热熔伤害提升25%",
            # 主C侧 damage.py 的同一个五件套：热熔伤害提升25%
            lambda attr, title, msg: attr.add_dmg_bonus(0.25, title, msg) if attr.char_attr == CHAR_ATTR_MOLTEN else None,
        ),
        _sonata(
            "幽夜隐匿之帷",
            "使下一个登场角色湮灭属性伤害加成提升15%",
            lambda attr, title, msg: attr.add_dmg_bonus(0.15, title, msg) if attr.char_attr == CHAR_ATTR_SINKING else None,
        ),
        # 以下为审计补录：这些套装原本只在主C自己的 phase_damage 里出现过，
        # 但同一套穿在队友身上同样会拐队友，所以一起收进目录。
        _sonata(
            "高天共奏之曲",
            "协同攻击命中敌人且暴击时，队伍中登场角色攻击力提升20%",
            # 主C侧 damage.py 的同一个五件套：协同攻击那条，攻击模板才吃
            # 队友侧的门只看队友有没有协同攻击角色（主C自己算不算由口径决定，见 _team_has_sync_strike）
            lambda attr, title, msg: (
                attr.add_atk_percent(0.2, title, msg) if attr.char_template == temp_atk and _team_has_sync_strike(attr) else None
            ),
        ),
        _sonata(
            "流云逝尽之空",
            "角色为敌人添加【风蚀效应】时，队伍中角色气动伤害提升15%",
            # 主C侧 damage.py 的同一个五件套：气动属性 + 【风蚀效应】都在才给
            lambda attr, title, msg: (
                attr.add_dmg_bonus(0.15, title, msg) if attr.char_attr == CHAR_ATTR_SIERRA and attr.env_aero_erosion else None
            ),
        ),
        _sonata(
            "奔狼燎原之焰",
            "施放共鸣解放时，队伍中角色热熔伤害提升15%",
            # 主C侧 damage.py 的同一个五件套：热熔属性才吃
            lambda attr, title, msg: attr.add_dmg_bonus(0.15, title, msg) if attr.char_attr == CHAR_ATTR_MOLTEN else None,
        ),
        _sonata(
            "息界同调之律",
            "队伍中角色声骸技能伤害加成提升4%*4",
            # 主C侧 damage.py 的同一个三件套：只对声骸技能伤害生效
            lambda attr, title, msg: attr.add_dmg_bonus(0.16, title, msg) if attr.char_damage == phantom_damage else None,
        ),
        _sonata(
            "剪心辑梦之影",
            "添加【偏移】时，队伍中角色谐度破坏增幅提升20点",
            # 主C侧 damage.py 的同一个五件套：要先添加【偏移】
            lambda attr, title, msg: attr.add_tune_break_boost(20, title, msg) if attr.is_env_shifting() else None,
        ),
        # 审计补录：这两套在主C侧的 phase_damage 里还没有实现，队友侧先按官方文案收录
        _sonata(
            "镜影流电之瞬",
            "为敌人添加【电磁效应】期间施放延奏技能后，下一个变奏技能登场的角色导电伤害提升25%",
            # 官方五件套：给的是导电伤害，只有导电主C吃得到
            lambda attr, title, msg: attr.add_dmg_bonus(0.25, title, msg) if attr.char_attr == CHAR_ATTR_VOID else None,
        ),
        _sonata(
            "茜染怀想之花",
            "为队伍中角色提供治疗时，队伍中角色攻击提升10%",
            # 只做治疗给的 10% 攻击；同奏/响应同奏那额外 15% 不并进来
            lambda attr, title, msg: attr.add_atk_percent(0.1, title, msg) if attr.char_template == temp_atk else None,
        ),
    )
}

ECHO_PRESETS: dict[str, EquipPreset] = {
    p.key: p
    for p in (
        _echo(
            "无常凶鹭",
            "施放延奏技能，则可使下一个变奏登场的角色伤害提升12%",
            lambda attr, title, msg: attr.add_dmg_bonus(0.12, title, msg),
        ),
        _echo(
            "无归的谬误",
            "全队角色攻击提升10%",
            lambda attr, title, msg: attr.add_atk_percent(0.1, title, msg) if attr.char_template == temp_atk else None,
        ),
        _echo(
            "鸣钟之龟",
            "全队角色10%的伤害提升",
            lambda attr, title, msg: attr.add_dmg_bonus(0.1, title, msg),
        ),
        _echo(
            "迷胧幻蛾",
            "施放延奏技能，则可使下一个变奏登场的角色攻击提升12%",
            # 官方文案（6000198）和 msg 都没有霜渐条件，只按攻击模板算
            lambda attr, title, msg: attr.add_atk_percent(0.12, title, msg) if attr.char_template == temp_atk else None,
        ),
        _echo(
            "海维夏",
            "使用后15秒内，使下一个变奏技能登场的角色全属性伤害加成提升10%",
            # 官方文案没有集谐条件，不用门
            lambda attr, title, msg: attr.add_dmg_bonus(0.1, title, msg),
        ),
        _echo(
            "达妮娅",
            "施放延奏技能，使下一个变奏登场的角色热熔伤害加成提升12%",
            # 官方文案（6000200）：热熔伤害加成，只有热熔主C吃得到
            lambda attr, title, msg: attr.add_dmg_bonus(0.12, title, msg) if attr.char_attr == CHAR_ATTR_MOLTEN else None,
        ),
        # 审计补录：同样能拐队友、之前没有收录的声骸
        _echo(
            "格洛犸图",
            "使用声骸技能后15秒内，若自身施放延奏技能，使下一个变奏技能登场的角色冷凝伤害加成提升12%",
            # 官方文案（6000195）：冷凝伤害加成，只有冷凝主C吃得到
            lambda attr, title, msg: attr.add_dmg_bonus(0.12, title, msg) if attr.char_attr == CHAR_ATTR_FREEZING else None,
        ),
        _echo(
            "绝息魄",
            "使用声骸技能后15秒内，若自身施放延奏技能，使下一个变奏技能登场的角色导电伤害加成提升12%",
            # 官方文案（6000224）：导电伤害加成，只有导电主C吃得到
            lambda attr, title, msg: attr.add_dmg_bonus(0.12, title, msg) if attr.char_attr == CHAR_ATTR_VOID else None,
        ),
    )
}

PRESETS: dict[str, dict[str, EquipPreset]] = {
    KIND_SONATA: SONATA_PRESETS,
    KIND_ECHO: ECHO_PRESETS,
}

# 武器：能做到「拐队友」的那些，记下用哪个行为触发。
# 武器增益一律由武器类自己算，这里只负责「能不能用、怎么触发」。
WEAPON_ACTIONS: dict[int, str] = {
    21010036: "cast_hit",  # 焰痕：重击延长后给队伍热熔伤害加成
    21010056: "do_action",  # 昙切
    21010066: "cast_healing",  # 宙算仪轨：治疗时给附近队伍暴击伤害
    21020046: "cast_skill",  # 血誓盟约：共鸣技能时给队伍气动伤害加深
    21020066: "cast_variation",  # 裁竹：变奏时给队伍声骸技能伤害
    21020107: "do_action",  # 沉冥：羁念给全队导电伤害加成
    21030015: "buff",  # 停驻之烟
    21030046: "do_action",  # 溢彩荧辉：普攻附加偏移时给队伍全伤害
    21030066: "do_action",  # 碎骨：附加骇破·偏移时给队伍攻击
    21050036: "skill_create_healing",  # 星序协响：治疗时给附近队伍攻击
    21050046: "cast_extension",  # 和光回唱：延奏时加深光噪效应伤害
    21050076: "do_action",  # 赝作的矮星
    21050086: "do_action",  # 存帧：给队伍攻击
    21050096: "do_action",  # 栖霞饮露：给附近队伍攻击
}

# ``do_action`` 系列（``do_action(func_list, attr, isGroup=False[, isSelf])``）的第一个
# 参数是「这次触发了哪些行为」；角色自己 _do_buff 里也是这么传的，队友用 武器=X 换上
# 这些武器时按下面几个触发，没写的按变奏技能算。
WEAPON_ACTION_FUNCS: dict[int, tuple[str, ...]] = {
    21020107: ("unison_jinian",),  # 沉冥：只有羁念那条是全队导电伤害加成
    21030046: ("cast_attack",),  # 溢彩荧辉：普攻为目标附加【偏移】时给队伍全伤害
}
WEAPON_ACTION_DEFAULT_FUNCS: tuple[str, ...] = (cast_variation,)


def preset_of(kind: str, key: str) -> EquipPreset | None:
    return PRESETS.get(kind, {}).get(key)


def preset_names(kind: str) -> list[str]:
    return list(PRESETS.get(kind, {}))


def apply_preset(attr, char_name: str, kind: str, key: str) -> bool:
    """按目录给 attr 加上某套合鸣 / 某个声骸的队伍增益。"""
    preset = preset_of(kind, key)
    if preset is None:
        return False
    preset.run(attr, char_name)
    return True


def apply_declared_equip(attr, char_name: str, declared: dict) -> None:
    """把角色声明里的默认合鸣 / 声骸按目录加上去。

    不知道「该不该生效」——生效条件写在预设自己的 apply 里（见 EquipPreset）。
    角色没声明的那一类直接跳过，用户覆盖由调用方处理。
    """
    for kind in EQUIP_KINDS:
        key = declared.get(kind)
        if key:
            apply_preset(attr, char_name, kind, key)


def declared_cases(declared: dict) -> tuple[dict, ...]:
    """角色声明的条件套（``teammate_equip["cases"]``），顺便挡住写错的键。

    条件套是「满足条件时改带另一套」：顶层还是默认，命中哪套就换哪套。
    键写错会静默变成「永远命中」，所以这里直接报错而不是忽略。
    """
    cases = declared.get(CASES_KEY) or ()
    if isinstance(cases, dict):
        raise TeamConfigError(f"队友装备的【{CASES_KEY}】要写成列表，每一项是一套条件装备")
    result: list[dict] = []
    for case in cases:
        if not isinstance(case, dict):
            raise TeamConfigError(f"队友装备的【{CASES_KEY}】里每一项都要是 {{条件…, 合鸣…, 声骸…}}")
        for key in case:
            if key not in CASE_KEYS and key not in CASE_EQUIP_KEYS:
                raise TeamConfigError(f"队友装备的条件套里不认识的键【{key}】")
        result.append(dict(case))
    return tuple(result)


def case_matches(attr, case: dict, chain: int = 0) -> bool:
    """条件套是否命中：写了的条件之间是 AND，一个都不写就是无条件命中。

    - ``env``      主角色身上的环境位为真（例如 ``env_fusion_burst``）
    - ``damage``   主角色当前的伤害类型（``attr.char_damage``）
    - ``template`` 主角色的模板（``attr.char_template``）
    - ``chain``    队友自己的共鸣链下限
    """
    env = case.get(CASE_ENV)
    if env and not getattr(attr, env, False):
        return False
    damage = case.get(CASE_DAMAGE)
    if damage and attr.char_damage != damage:
        return False
    template = case.get(CASE_TEMPLATE)
    if template and attr.char_template != template:
        return False
    need_chain = case.get(CASE_CHAIN)
    return need_chain is None or int(chain) >= int(need_chain)


def match_case(attr, declared: dict, chain: int = 0) -> dict | None:
    """按顺序取第一个所有条件都命中的条件套，没有命中的返回 None。"""
    for case in declared_cases(declared):
        if case_matches(attr, case, chain):
            return case
    return None


def resolve_declared_equip(attr, declared: dict, chain: int = 0) -> dict:
    """解析这次实际要带的装备：顶层默认 + 命中的条件套覆盖写了的键。

    只读 attr 上当时的状态和队友自己的共鸣链，不写任何数值；施加还是走目录。
    """
    equip = {kind: declared.get(kind) for kind in CASE_EQUIP_KEYS}
    case = match_case(attr, declared, chain)
    if case:
        for kind in CASE_EQUIP_KEYS:
            if case.get(kind):
                equip[kind] = case[kind]
    return equip


def weapon_action(weapon_id: int | None) -> str | None:
    return WEAPON_ACTIONS.get(int(weapon_id)) if weapon_id else None


def weapon_name(weapon_id: int | None) -> str | None:
    if not weapon_id:
        return None
    from .abstract import WavesWeaponRegister

    weapon_clz = WavesWeaponRegister.find_class(int(weapon_id))
    return getattr(weapon_clz, "name", None) if weapon_clz else None


def weapon_options() -> list[tuple[int, str]]:
    """所有可选的「能拐队友」的武器：(id, 名称)。"""
    options = []
    for weapon_id in WEAPON_ACTIONS:
        name = weapon_name(weapon_id)
        if name:
            options.append((weapon_id, name))
    options.sort(key=lambda item: item[1])
    return options


def resolve_weapon_id(value: Any) -> int | None:
    """把用户填的武器名或武器 id 解析成武器 id（只认目录里能拐队友的武器）。"""
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value in WEAPON_ACTIONS else None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        candidate = int(text)
        return candidate if candidate in WEAPON_ACTIONS else None
    for weapon_id, name in weapon_options():
        if name == text:
            return weapon_id
    return None


def apply_weapon(attr, weapon_id: int, action: str, reson_level: int, is_group: bool) -> bool:
    """按角色声明的用法施加对应武器的增益。

    武器行为有两种签名，都要能调：

    - ``cast_xxx(attr, isGroup=False)`` 之类：直接作用在 attr 上
    - ``do_action(func_list, attr, isGroup=False[, isSelf])``：先给一个「这次触发了
      哪些行为」的列表（见 ``WEAPON_ACTION_FUNCS``），再传 attr。队友拿这把武器时
      增益是给主C的，所以 ``isSelf`` 一律关掉 —— 和角色自己 _do_buff 里的写法一致。
    """
    from .abstract import WavesWeaponRegister

    weapon_clz = WavesWeaponRegister.find_class(int(weapon_id))
    if weapon_clz is None:
        return False
    weapon = weapon_clz(int(weapon_id), 90, 6, reson_level)
    method = getattr(weapon, action, None)
    if not callable(method):
        return False
    params = inspect.signature(method).parameters
    if "func_list" in params:
        func_list = list(WEAPON_ACTION_FUNCS.get(int(weapon_id), WEAPON_ACTION_DEFAULT_FUNCS))
        if "isSelf" in params:
            method(func_list, attr, is_group, isSelf=False)
        else:
            method(func_list, attr, is_group)
    else:
        method(attr, is_group)
    return True


CATEGORY_CHARACTER = "character"
CATEGORY_OUTRO = "outro"
CATEGORY_SONATA = "sonata"
CATEGORY_ECHO = "echo"

ALL_CATEGORIES = (CATEGORY_CHARACTER, CATEGORY_OUTRO, CATEGORY_SONATA, CATEGORY_ECHO)

CATEGORY_LABELS: dict[str, str] = {
    CATEGORY_CHARACTER: "角色自身增益",
    CATEGORY_OUTRO: "延奏技能",
    CATEGORY_SONATA: "合鸣效果",
    CATEGORY_ECHO: "声骸技能",
}


SONATA_MARK = "合鸣效果-"
ECHO_MARK = "声骸技能-"
NEXT_MARKERS = ("下一位", "下一个")

# 合鸣/声骸/武器的两种特殊取值
EQ_DEFAULT = "default"
EQ_NONE = "none"

_MAX_MEMBERS = 2


class TeamConfigError(ValueError):
    """自定义配队配置错误（面向用户的提示信息）。"""


@dataclass
class TeamMember:
    """一名自定义队友的配置。"""

    role_id: int
    chain: int = 0
    reson_level: int = 1
    # 总开关：关闭后该队友不提供任何增益
    character_buff: bool = True
    # 分类开关
    outro: bool = True
    # "default" 用角色声明里的默认 | "none" 关 | 其它值为替换的预设名
    sonata: str = EQ_DEFAULT
    echo: str = EQ_DEFAULT
    # 是否计算专武
    weapon: bool = True
    # 指定武器（id），None 表示用声明里的默认
    weapon_id: int | None = None
    # 角色特有状态覆盖，默认值由各角色 _do_buff 决定
    states: dict[str, Any] = field(default_factory=dict)
    # validate_team 后填充，用于展示
    name: str = ""

    def describe(self) -> str:
        if self.weapon_id:
            weapon_text = f"武器={weapon_name(self.weapon_id) or self.weapon_id}"
        elif self.weapon:
            weapon_text = f"专武精{self.reson_level}"
        else:
            weapon_text = "不计专武"
        parts = [f"{self.chain}链", weapon_text]
        if not self.character_buff:
            parts.append("无增益")
            return "·".join(parts)
        if not self.outro:
            parts.append("无延奏")
        if self.sonata == EQ_NONE:
            parts.append("无合鸣")
        elif self.sonata != EQ_DEFAULT:
            parts.append(f"合鸣={self.sonata}")
        if self.echo == EQ_NONE:
            parts.append("无声骸")
        elif self.echo != EQ_DEFAULT:
            parts.append(f"声骸={self.echo}")
        for key, value in self.states.items():
            parts.append(f"{key}={_format_state(value)}")
        return "·".join(parts)


def _format_state(value: Any) -> str:
    if isinstance(value, bool):
        return "开" if value else "关"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _char_registry():
    from .abstract import WavesCharRegister

    return WavesCharRegister


def teammate_states(role_id: int) -> dict[str, dict]:
    """某角色声明的「可调状态」，来源是 Char_xxxx.teammate_states。"""
    char_clz = _char_registry().find_class(int(role_id))
    if char_clz is None:
        return {}
    declared = getattr(char_clz, "teammate_states", None)
    if not isinstance(declared, dict):
        return {}
    return {key: dict(spec) for key, spec in declared.items()}


def teammate_equip(role_id: int) -> dict:
    """某角色声明的默认装备，来源是 Char_xxxx.teammate_equip。

    只声明角色真正写死过的东西：没写武器就没有 ``weapon`` 键。
    """
    char_clz = _char_registry().find_class(int(role_id))
    if char_clz is None:
        return {}
    declared = getattr(char_clz, "teammate_equip", None)
    return dict(declared) if isinstance(declared, dict) else {}


def state_spec(role_id: int, key: str) -> dict | None:
    return teammate_states(role_id).get(key)


def state_default(role_id: int, key: str) -> Any:
    spec = state_spec(role_id, key)
    if not spec:
        return None
    return spec.get("default")


def state_hint(role_id: int, key: str) -> str:
    """把声明渲染成一行人类可读的范围说明，例如 "0~10，默认10"。"""
    spec = state_spec(role_id, key)
    if not spec:
        return ""
    kind = spec.get("type", "int")
    default = spec.get("default")
    if kind == "bool":
        return f"开/关，默认{'开' if default is not False else '关'}"
    if kind == "enum":
        choices = "、".join(spec.get("choices", ()))
        return f"{choices}，默认{default}"
    low, high = spec.get("min"), spec.get("max")
    span = f"{_format_state(low)}~{_format_state(high)}" if low is not None and high is not None else "数值"
    return f"{span}，默认{_format_state(default)}"


def supported_teammate_ids() -> set[int]:
    """所有实现了队友增益（重写了 _do_buff）的角色。"""
    from .abstract import CharAbstract

    base = CharAbstract._do_buff
    result: set[int] = set()
    for role_id, char_clz in _char_registry()._id_cls_map.items():
        if getattr(char_clz, "_do_buff", None) is not base:
            result.add(int(role_id))
    return result


def char_name(role_id: int) -> str:
    char_clz = _char_registry().find_class(role_id)
    if char_clz is None:
        return str(role_id)
    return char_clz.name or str(role_id)


def is_registered(role_id: int) -> bool:
    """该角色是否已经在注册表里（注册表在 bot 启动时才填充）。"""
    try:
        return _char_registry().find_class(int(role_id)) is not None
    except (TypeError, ValueError):
        return False


def coerce_state(role_id: int, key: str, value: Any) -> Any:
    """把用户输入的状态值转成规范形式；不合法或该角色没声明时抛 TeamConfigError。"""
    spec = state_spec(role_id, key)
    if spec is None:
        raise TeamConfigError(f"该队友不支持状态【{key}】")
    return _check_state(char_name(role_id), key, spec, value)


def validate_team(members: Any, main_role_id: int | None = None) -> tuple[TeamMember, ...]:
    """校验并补全队友配置，非法配置抛出 TeamConfigError。"""
    if members is None:
        raise TeamConfigError("没有需要校验的队友配置")

    members = tuple(members)
    if not members:
        raise TeamConfigError("请至少填写1名队友")
    if len(members) > _MAX_MEMBERS:
        raise TeamConfigError(f"自定义配队最多支持{_MAX_MEMBERS}名队友")

    supported = supported_teammate_ids()
    seen: set[int] = set()
    result: list[TeamMember] = []
    for member in members:
        role_id = int(member.role_id)
        name = char_name(role_id)
        chain = int(getattr(member, "chain", 0) or 0)
        reson_level = int(getattr(member, "reson_level", 1) or 1)
        sonata = getattr(member, "sonata", EQ_DEFAULT) or EQ_DEFAULT
        echo = getattr(member, "echo", EQ_DEFAULT) or EQ_DEFAULT
        if role_id in seen:
            raise TeamConfigError(f"队友【{name}】重复")
        if main_role_id is not None and role_id == int(main_role_id):
            raise TeamConfigError(f"队友【{name}】不能是当前计算伤害的角色本身")
        if role_id not in supported:
            raise TeamConfigError(f"【{name}】暂不支持作为自定义队友（没有可用的辅助增益模型）")
        if not 0 <= chain <= 6:
            raise TeamConfigError(f"队友【{name}】共鸣链范围是0至6")
        if not 1 <= reson_level <= 5:
            raise TeamConfigError(f"队友【{name}】武器精炼范围是1至5")

        declared = teammate_equip(role_id)
        sonata = _check_equip_choice(name, "合鸣", KIND_SONATA, sonata)
        echo = _check_equip_choice(name, "声骸", KIND_ECHO, echo)

        weapon_id = getattr(member, "weapon_id", None)
        if weapon_id:
            resolved = resolve_weapon_id(weapon_id)
            if resolved is None:
                options = "、".join(name for _id, name in weapon_options())
                raise TeamConfigError(f"队友【{name}】找不到能用的武器【{weapon_id}】，可填：{options}，或填 关")
            weapon_id = resolved
        else:
            weapon_id = None

        states = dict(getattr(member, "states", None) or {})
        allowed = teammate_states(role_id)
        for key, value in states.items():
            if key not in allowed:
                if allowed:
                    raise TeamConfigError(f"队友【{name}】不支持状态【{key}】，可用：{'、'.join(allowed)}")
                raise TeamConfigError(f"队友【{name}】不支持任何状态设置")
            states[key] = _check_state(name, key, allowed[key], value)

        seen.add(role_id)
        result.append(
            TeamMember(
                role_id=role_id,
                chain=chain,
                reson_level=reson_level,
                character_buff=bool(getattr(member, "character_buff", True)),
                outro=bool(getattr(member, "outro", True)),
                sonata=sonata,
                echo=echo,
                weapon=bool(getattr(member, "weapon", True)),
                weapon_id=weapon_id,
                states=states,
                name=name,
            )
        )
    return tuple(result)


def _check_equip_choice(name: str, label: str, kind: str, choice: str) -> str:
    """合鸣/声骸的取值：default / none / 目录里存在的预设名。"""
    if choice in (EQ_DEFAULT, EQ_NONE):
        return choice
    if choice not in preset_names(kind):
        raise TeamConfigError(
            f"队友【{name}】的{label}【{choice}】不在可用列表里，可填：{'、'.join(preset_names(kind))}，或填 关"
        )
    return choice


def _check_state(name: str, key: str, spec: dict, value: Any) -> Any:
    """按角色自己声明的状态规格校验取值。"""
    kind = spec.get("type", "int")

    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value > 0
        if isinstance(value, str):
            return value.strip().casefold() in ("开", "是", "true", "1")
        raise TeamConfigError(f"队友【{name}】的【{key}】只能填写开/关")

    if kind == "enum":
        choices = tuple(spec.get("choices", ()))
        if value not in choices:
            raise TeamConfigError(f"队友【{name}】的【{key}】只能是{'/'.join(choices)}")
        return value

    low, high = spec.get("min"), spec.get("max")
    try:
        number = float(value)
    except (TypeError, ValueError) as e:
        raise TeamConfigError(f"队友【{name}】的【{key}】需要填写数字") from e
    if number != number or number in (float("inf"), float("-inf")):
        raise TeamConfigError(f"队友【{name}】的【{key}】不是合法数值")
    if low is not None and number < low:
        raise TeamConfigError(f"队友【{name}】的【{key}】不能小于{_format_state(low)}")
    if high is not None and number > high:
        raise TeamConfigError(f"队友【{name}】的【{key}】不能大于{_format_state(high)}")
    return int(number) if number.is_integer() else number


def describe_team(members: tuple[TeamMember, ...] | None) -> list[str]:
    """把配队配置拆成适合逐行展示的文本。"""
    if not members:
        return ["自定义配队：无"]
    rows = ["自定义配队（仅本次模拟，不参与排名）"]
    for index, member in enumerate(members, start=1):
        rows.append(f"队友{index}：{member.name}　{member.describe()}")
    return rows


def disabled_categories(member: TeamMember) -> set[str]:
    if not member.character_buff:
        return set(ALL_CATEGORIES)
    disabled: set[str] = set()
    if not member.outro:
        disabled.add(CATEGORY_OUTRO)
    if member.sonata == "none":
        disabled.add(CATEGORY_SONATA)
    if member.echo == "none":
        disabled.add(CATEGORY_ECHO)
    return disabled


def _categorize(title: str) -> str:
    if "延奏" in title:
        return CATEGORY_OUTRO
    if SONATA_MARK in title:
        return CATEGORY_SONATA
    if ECHO_MARK in title:
        return CATEGORY_ECHO
    return CATEGORY_CHARACTER


def _title_msg(func_name: str, args: tuple, kwargs: dict) -> tuple[str, str]:
    if func_name == "add_effect":
        title = args[0] if args else kwargs.get("title", "")
        msg = args[1] if len(args) > 1 else kwargs.get("msg", "")
    else:
        title = args[1] if len(args) > 1 else kwargs.get("title", "")
        msg = args[2] if len(args) > 2 else kwargs.get("msg", "")
    title = title if isinstance(title, str) else str(title or "")
    msg = msg if isinstance(msg, str) else str(msg or "")
    return title, msg


class _BuffFilter:
    """调用期间拦截 attr.add_* 写入，用于按分类开关放行/拦截，并可选记录标题。"""

    def __init__(self, attr, disabled: set[str], capture: dict | None = None):
        self.attr = attr
        self.disabled = disabled
        self.capture = capture
        self._cls = type(attr)
        self._patched: dict[str, Any] = {}

    def __enter__(self):
        attr = self.attr
        disabled = self.disabled
        capture = self.capture

        def make_wrapper(func_name: str, original):
            def wrapper(self_attr, *args, **kwargs):
                if self_attr is not attr:
                    return original(self_attr, *args, **kwargs)
                title, msg = _title_msg(func_name, args, kwargs)
                category = _categorize(title)
                if capture is not None:
                    capture.setdefault(category, []).append((title, msg))
                if category in disabled:
                    return self_attr
                return original(self_attr, *args, **kwargs)

            wrapper.__name__ = func_name
            return wrapper

        for name in _add_method_names():
            if not hasattr(self._cls, name):
                continue
            original = getattr(self._cls, name)
            if not callable(original):
                continue
            self._patched[name] = original
        for name, original in self._patched.items():
            setattr(self._cls, name, make_wrapper(name, original))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for name, original in self._patched.items():
            setattr(self._cls, name, original)
        self._patched.clear()
        return False


class _WeaponSuppressor:
    """调用期间让武器注册表查找返回空，用于关闭专武增益。"""

    _MISSING = object()

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._registry = None
        self._original: Any = self._MISSING

    def __enter__(self):
        if self.enabled:
            return self
        from .abstract import WavesWeaponRegister

        self._registry = WavesWeaponRegister
        self._original = WavesWeaponRegister.__dict__.get("find_class", self._MISSING)

        def _find_nothing(_id):
            return None

        WavesWeaponRegister.find_class = staticmethod(_find_nothing)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        registry = self._registry
        if registry is not None:
            if self._original is self._MISSING:
                try:
                    delattr(registry, "find_class")
                except AttributeError:
                    pass
            else:
                registry.find_class = self._original
        self._registry = None
        return False


def _apply_pending_equip(attr, char_name: str, equip: dict, pending: list[str], skip: tuple[str, ...] = ()) -> None:
    """把 ``pending`` 里还没生效的合鸣 / 声骸按目录施加，生效的从 ``pending`` 划掉。

    顺序就是 ``pending`` 的顺序（固定先合鸣后声骸）：两套都写同一个乘区时，
    加法顺序会影响浮点结果，不能按 set 的顺序来。``skip`` 里的那几类这一趟不动，
    留给下一趟（被条件套替换掉的默认装备就是这样错开位置的）。

    记录用的是 ``_BuffFilter`` 的 capture，所以「施加到真 attr 上」和「只空跑
    收集标题」两种模式都能判断有没有真的生效。
    """
    capture: dict[str, list[tuple[str, str]]] = {}
    with _BuffFilter(attr, set(), capture):
        for kind in list(pending):
            if kind in skip:
                continue
            key = equip.get(kind)
            if not key:
                pending.remove(kind)
                continue
            apply_preset(attr, char_name, kind, key)
            if capture.get(kind):
                pending.remove(kind)


class _EquipAtWeaponLookup:
    """在角色查自己的武器之前，把条件套换上的装备补上。

    条件套（``teammate_equip["cases"]``）原本写死在 ``_do_buff`` 的末尾、专武那几行
    上面：位置对齐才不会改 ``atk_percent`` / ``dmg_bonus`` 的浮点求和顺序，说明里的
    词条顺序也不会变。只有真命中条件套的角色才会装上这个钩子，其它角色不受影响。
    """

    _MISSING = object()

    def __init__(self, flush: Callable[[], None]):
        self.flush = flush
        self._registry: Any = None
        self._original: Any = self._MISSING

    def __enter__(self):
        from .abstract import WavesWeaponRegister

        self._registry = WavesWeaponRegister
        self._original = WavesWeaponRegister.__dict__.get("find_class", self._MISSING)
        # 可能已经被别人包过一层（_WeaponSuppressor / _WeaponLookupRecorder），
        # 所以取绑定后的方法原样往下传，不能只看自己类里的 __dict__
        original = WavesWeaponRegister.find_class
        flush = self.flush

        def _find(target_cls, weapon_id):
            flush()
            return original(weapon_id)

        WavesWeaponRegister.find_class = classmethod(_find)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        registry = self._registry
        if registry is not None:
            if self._original is self._MISSING:
                try:
                    delattr(registry, "find_class")
                except AttributeError:
                    pass
            else:
                registry.find_class = self._original
        self._registry = None
        return False


def _buff_callable(instance):
    """一名角色作为队友时的完整增益：目录里声明的合鸣 / 声骸 + ``_do_buff``。

    合鸣 / 声骸统一走目录，角色代码里不再重复写一遍；这样「默认装备」和
    「换装备」是同一条路径，一份数值只维护一次。

    施加分两趟，先装备、后自己：

    1. 先按目录加一次。位置和原先写死在 ``_do_buff`` 里的那几行一致（基本都在
       角色自己的武器之前），这样 ``atk_percent`` 之类的浮点求和顺序不变 ——
       顺序一变 ``effect_attack`` 里的 ``int()`` 截断就可能差 1 点，伤害跟着动。
    2. ``_do_buff`` 之后再补一次。有个别套装 / 声骸的条件靠角色自己开的环境位
       （例如琳奈的【集谐·偏移】打开 ``env_tune_strain``），第一趟时还不成立；
       第一趟已经生效的不会再补第二遍，所以不会算两次。

    条件套（``teammate_equip["cases"]``）每趟都按当时的 attr 重新解析：命中就换成
    那套，没命中的键仍用顶层默认。被换掉的那几类第一趟先不加 —— 它们原本写在
    ``_do_buff`` 末尾、专武上面，所以留到那一刻再补，位置同样对齐。

    返回的函数带 ``functools.wraps``，``inspect.signature`` 仍能看出原方法
    收不收 ``states``，``_buff_kwargs`` 不受影响。
    """
    buff = getattr(instance, "_do_buff", None)
    if not callable(buff):
        raise TeamConfigError(f"【{getattr(instance, 'name', '该角色')}】没有可用的辅助增益模型")

    declared = getattr(instance, "teammate_equip", None)
    declared = dict(declared) if isinstance(declared, dict) else {}
    char_name = getattr(instance, "name", None) or ""

    @functools.wraps(buff)
    def _do_buff_with_equip(attr, *args, **kwargs):
        chain = kwargs.get("chain") or 0
        case = match_case(attr, declared, chain) or {}
        deferred = tuple(kind for kind in EQUIP_KINDS if case.get(kind))
        pending = list(EQUIP_KINDS)
        _apply_pending_equip(attr, char_name, resolve_declared_equip(attr, declared, chain), pending, deferred)

        flushed = False

        def flush() -> None:
            nonlocal flushed
            if flushed:
                return
            flushed = True
            _apply_pending_equip(attr, char_name, resolve_declared_equip(attr, declared, chain), pending)

        if deferred:
            with _EquipAtWeaponLookup(flush):
                buff(attr, *args, **kwargs)
        else:
            buff(attr, *args, **kwargs)
        flush()

    return _do_buff_with_equip


_SIGNATURE_CACHE: dict[Any, bool] = {}


def _accepts_states(func) -> bool:
    key = getattr(func, "__func__", func)
    cached = _SIGNATURE_CACHE.get(key)
    if cached is None:
        try:
            cached = "states" in inspect.signature(func).parameters
        except (TypeError, ValueError):
            cached = False
        _SIGNATURE_CACHE[key] = cached
    return cached


def _buff_kwargs(func, member: TeamMember) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"chain": member.chain, "resonLevel": member.reson_level, "isGroup": True}
    if member.states and _accepts_states(func):
        kwargs["states"] = dict(member.states)
    return kwargs


def _capture_member(attr, member: TeamMember) -> dict[str, list[tuple[str, str]]]:
    """空跑一遍队友增益，只收集标题，不写入任何数值。"""
    char_clz = _char_registry().find_class(member.role_id)
    if char_clz is None:
        raise TeamConfigError(f"未找到角色【{member.role_id}】")
    func = _buff_callable(char_clz())
    capture: dict[str, list[tuple[str, str]]] = {}
    with _BuffFilter(attr, set(ALL_CATEGORIES), capture):
        func(attr, **_buff_kwargs(func, member))
    return capture


def validate_conflicts(attr, members: tuple[TeamMember, ...], captures: dict[int, dict] | None = None) -> None:
    """在真正施加增益前，用空跑结果检查配队冲突。

    替换了合鸣/声骸的队友按「替换后的名字」参与查重，否则两个人都换成同一套会算重。
    """
    captures = captures or {}
    sonata_owner: dict[str, str] = {}
    echo_owner: dict[str, str] = {}
    next_outro: list[str] = []
    for member in members:
        if not member.character_buff:
            continue
        captured = captures.get(member.role_id) or _capture_member(attr, member)
        declared = teammate_equip(member.role_id)
        equipped = resolve_declared_equip(attr, declared, member.chain)
        for kind, chosen, owner_map, mark, label in (
            (KIND_SONATA, member.sonata, sonata_owner, SONATA_MARK, "合鸣"),
            (KIND_ECHO, member.echo, echo_owner, ECHO_MARK, "声骸"),
        ):
            if chosen == EQ_NONE:
                continue
            if chosen != EQ_DEFAULT and chosen != equipped.get(kind):
                if captured.get(kind):
                    names = [chosen]
                else:
                    names = []
            else:
                names = [title.split(mark, 1)[1] for title, _msg in captured.get(kind, []) if mark in title]
            for name in names:
                owner = owner_map.setdefault(name, member.name)
                if owner != member.name:
                    raise TeamConfigError(
                        f"【{owner}】和【{member.name}】都使用了同名{label}【{name}】，请对其中一位设置 {label}=关 后重试"
                    )
        if member.outro:
            if any(any(marker in msg for marker in NEXT_MARKERS) for _title, msg in captured.get(CATEGORY_OUTRO, [])):
                next_outro.append(member.name)
    if len(next_outro) > 1:
        raise TeamConfigError(f"{'、'.join(next_outro)}的延奏都只作用于「下一位登场角色」，请对其中一位设置 延奏=关 后重试")


def _apply_member(attr, member: TeamMember, captured: dict | None = None) -> None:
    char_clz = _char_registry().find_class(member.role_id)
    if char_clz is None:
        raise TeamConfigError(f"未找到角色【{member.role_id}】")
    func = _buff_callable(char_clz())
    # 生效条件（含条件套）按当时的 attr 解析：用户显式换装备时，比的应该是
    # 「现在这套」而不是顶层默认
    declared = teammate_equip(member.role_id)
    equipped = resolve_declared_equip(attr, declared, member.chain)

    disabled = disabled_categories(member)
    replacements: list[tuple[str, str]] = []
    if captured is None:
        captured = _capture_member(attr, member)
    for kind, chosen in ((KIND_SONATA, member.sonata), (KIND_ECHO, member.echo)):
        if chosen in (EQ_DEFAULT, EQ_NONE) or chosen == equipped.get(kind):
            # 默认（或与声明相同）：由 _buff_callable 按目录施加，门在预设里
            continue
        if kind in declared:
            # 角色本来就有这一部分：只在「原本当前条件下确实会提供」时才替换，
            # 免得替换绕过预设自己的生效条件
            if not captured.get(kind):
                continue
            # 关掉声明的那套，换成用户选的
            disabled.add(kind)
        # 角色本来没有这一部分（例如没写套装的角色），任何人都可以自己加一套
        replacements.append((kind, chosen))

    weapon_id = member.weapon_id
    declared_weapon = equipped.get(KIND_WEAPON) or {}
    weapon_override = bool(weapon_id) and weapon_id != declared_weapon.get("id")

    with _WeaponSuppressor(member.weapon and not weapon_override):
        with _BuffFilter(attr, disabled):
            func(attr, **_buff_kwargs(func, member))

    for kind, chosen in replacements:
        apply_preset(attr, member.name, kind, chosen)

    if weapon_override and weapon_id:
        action = weapon_action(weapon_id)
        if not action:
            raise TeamConfigError(f"【{member.name}】用不了【{weapon_name(weapon_id) or weapon_id}】这把武器")
        if not apply_weapon(attr, weapon_id, action, member.reson_level, True):
            raise TeamConfigError(f"【{member.name}】无法触发该武器（缺少 {action} 行为），请换回默认或填 关")


def default_member(spec) -> TeamMember:
    """把 ``(角色id, 共鸣链, 精炼)`` 这种简写变成 TeamMember。"""
    role_id, chain, reson_level = spec
    return TeamMember(role_id=int(role_id), chain=int(chain), reson_level=int(reson_level))


def apply_teammates(attr) -> None:
    """应用队友增益。伤害函数通过 ``attr.set_teammate_buff()`` 调到这里。

    一次计算只应用一次：条目可能在不同层级各调一次，重复应用会叠加。
    """
    if getattr(attr, "_teammate_applied", False):
        return
    attr._teammate_applied = True

    members = getattr(attr, "_teammate_config", None) or ()
    members = tuple(m if isinstance(m, TeamMember) else default_member(m) for m in members)
    if not members:
        return

    # 有队友就是组队模式：武器 / 声骸 / 协同攻击那几处按组队算
    attr.group_mode = True
    members = _fill_names(members)
    captures: dict[int, dict] = {}
    for member in members:
        captures[member.role_id] = _capture_member(attr, member)
    validate_conflicts(attr, members, captures)

    for member in members:
        attr.add_teammate(member.role_id)

    for member in members:
        _apply_member(attr, member, captures.get(member.role_id))


def _fill_names(members: tuple[TeamMember, ...]) -> tuple[TeamMember, ...]:
    """补上角色名，展示和报错都要用。"""
    filled = []
    for member in members:
        if not member.name:
            member = TeamMember(**{**member.__dict__, "name": char_name(member.role_id)})
        filled.append(member)
    return tuple(filled)


def attach_teammate(attr, members) -> None:
    """挂队友配置：换队友或条目自带的默认配队。

    先挂的生效，所以用户换队友时条目里的默认配队不会顶掉它。
    配队说明在这里写一次（聚合型伤害函数会把 attr 复制几份，写在这里才不会重复）。
    """
    if getattr(attr, "_teammate_config", None):
        return
    # 兼容三种写法：一组 TeamMember、单个 (id, 链, 精炼)、多个 (id, 链, 精炼)
    if len(members) == 1 and isinstance(members[0], (list, tuple)):
        first = members[0][0] if members[0] else None
        if isinstance(first, (TeamMember, list, tuple)):
            members = tuple(members[0])
    config = tuple(m if isinstance(m, TeamMember) else default_member(m) for m in members)
    attr._teammate_config = config
    add_team_rows(attr, _fill_names(config))


def add_team_rows(attr, members: tuple[TeamMember, ...]) -> None:
    """列出这次上了谁：队友1·莫宁 / 0链·专武精1（后面跟自定义的状态、装备等）。

    ``_teammate_rows_added`` 是给聚合型伤害函数用的：它们会把 attr 复制几份分别算，
    没有这个标记同一段说明会被拼进来好几次。
    """
    if getattr(attr, "_teammate_rows_added", False):
        return
    attr._teammate_rows_added = True
    for index, member in enumerate(members, start=1):
        attr.add_effect(f"队友{index}·{member.name}", member.describe())


def _has_config(attr) -> bool:
    return getattr(attr, "_teammate_config", None) is not None


_CHAIN_PROBES = (0, 1, 2, 3, 4, 5, 6)


_ENV_LABELS: dict[str, str] | None = None


_ENV_PROBES: tuple[dict[str, bool], ...] | None = None


_ATTR_PROBES: tuple[str, ...] | None = None


def _attr_probes() -> tuple[str, ...]:
    """可作为主C的属性。0 是物理，目前没有可选角色。"""
    global _ATTR_PROBES
    if _ATTR_PROBES is None:
        from ..resource.constant import ATTRIBUTE_ID_MAP

        _ATTR_PROBES = tuple(name for attr_id, name in sorted(ATTRIBUTE_ID_MAP.items()) if attr_id)
    return _ATTR_PROBES


def _env_labels() -> dict[str, str]:
    """环境位 -> 中文名，直接读 set_env_* 的文档字符串。"""
    global _ENV_LABELS
    if _ENV_LABELS is None:
        from .damage import DamageAttribute

        _ENV_LABELS = {}
        for name in dir(DamageAttribute):
            if not name.startswith("set_env_"):
                continue
            doc = (getattr(DamageAttribute, name).__doc__ or "").strip()
            if doc:
                _ENV_LABELS[name[len("set_") :]] = doc
    return _ENV_LABELS


def _env_probes() -> tuple[dict[str, bool], ...]:
    """每个基础效应探两档：只开效应 / 效应+伤害加深。

    加深档一定带上基础效应，否则会造出「加深开着、效应没开」的假状态。
    """
    global _ENV_PROBES
    if _ENV_PROBES is None:
        labels = _env_labels()
        probes: list[dict[str, bool]] = [{}]
        for flag in labels:
            base = flag[: -len("_deepen")] if flag.endswith("_deepen") else flag
            candidate = {base: True}
            if f"{base}_deepen" in labels:
                candidate[f"{base}_deepen"] = True
            if candidate not in probes:
                probes.append(candidate)
        _ENV_PROBES = tuple(probes)
    return _ENV_PROBES


_ADD_METHOD_NAMES: list[str] | None = None


def _add_method_names() -> list[str]:
    """DamageAttribute 上所有 add_* 方法名（缓存，避免每次空跑都重新扫）。"""
    global _ADD_METHOD_NAMES
    if _ADD_METHOD_NAMES is None:
        from .damage import DamageAttribute

        _ADD_METHOD_NAMES = [
            name for name in dir(DamageAttribute) if name.startswith("add_") and callable(getattr(DamageAttribute, name))
        ]
    return _ADD_METHOD_NAMES


def _damage_probes() -> list[tuple[str, str]]:
    """探测用的伤害类型 -> 中文名，取自 utils/damage/utils.py 的 damage_name_map。"""
    from .utils import damage_name_map

    return list(damage_name_map.items())


class _WeaponLookupRecorder:
    """记录 _do_buff 期间查询了哪些武器 id，即该队友的预设专武。"""

    _MISSING = object()

    def __init__(self):
        self.ids: list[int] = []
        self._original: Any = self._MISSING

    def __enter__(self):
        from .abstract import WavesWeaponRegister

        self._registry = WavesWeaponRegister
        # 恢复用原始属性（可能是别人包的一层，也可能压根没有——find_class 继承自
        # WavesRegister，__dict__ 里通常查不到）；转发则必须用 getattr 取绑定后的方法，
        # 只看 __dict__ 会永远拿到 None，队友专武就被静默跳过。
        self._original = WavesWeaponRegister.__dict__.get("find_class", self._MISSING)
        recorded = self.ids
        original = WavesWeaponRegister.find_class

        def _find(target_cls, weapon_id):
            recorded.append(int(weapon_id))
            return original(weapon_id)

        WavesWeaponRegister.find_class = classmethod(_find)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        registry = getattr(self, "_registry", None)
        if registry is not None:
            if self._original is self._MISSING:
                try:
                    delattr(registry, "find_class")
                except AttributeError:
                    pass
            else:
                registry.find_class = self._original
        return False


def _scratch_attr(damage_type: str, char_attr: str, extra: dict):
    from .damage import DamageAttribute

    attr = DamageAttribute(char_template="temp_atk", char_damage=damage_type, char_attr=char_attr)
    for key, value in extra.items():
        setattr(attr, key, value)
    return attr
