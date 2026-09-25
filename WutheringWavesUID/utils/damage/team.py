"""队友说明图（``ww队友配置``）的数据来源。

探测逻辑放这里，需要的队友增益定义（装备目录、状态声明）从 buff.py 取，
不重复维护第二份。
"""

from .buff import (
    _CHAIN_PROBES,
    ALL_CATEGORIES,
    CASE_CHAIN,
    CASE_DAMAGE,
    CASE_ENV,
    CASE_TEMPLATE,
    CATEGORY_LABELS,
    EQUIP_KINDS,
    KIND_ECHO,
    KIND_LABELS,
    KIND_SONATA,
    KIND_WEAPON,
    TeamConfigError,
    TeamMember,
    _attr_probes,
    _buff_callable,
    _buff_kwargs,
    _BuffFilter,
    _char_registry,
    _damage_probes,
    _env_labels,
    _env_probes,
    _format_state,
    _scratch_attr,
    _WeaponLookupRecorder,
    char_name,
    declared_cases,
    preset_names,
    state_hint,
    supported_teammate_ids,
    teammate_equip,
    teammate_states,
    weapon_options,
)
from .utils import temp_atk, temp_def, temp_life

# --------------------------------------------------------------- 配置自动生成
#
# 「ww队友配置」说明图里的内容全部由这里生成，不手写：
#   - 能开关哪几类        -> 空跑一遍 _do_buff，看每一类实际写了什么
#   - 预设专武是哪把      -> 记录 _do_buff 期间查询了哪个武器 id
#   - 每条增益的生效条件  -> 遍历「主角色伤害类型 × 属性 × 共鸣链」探测
#   - 可调状态            -> 直接读 Char_xxxx.teammate_states 声明


# 探测用的两个轴都取自现有配置，不手写：
#   主C属性  -> utils/resource/constant.py 的 ATTRIBUTE_ID_MAP
#   环境状态 -> DamageAttribute 上 set_env_* 的文档字符串（"光噪效应" 之类）


def detect_teammate(role_id: int) -> dict:
    """空跑探测一名队友实际提供什么、在什么条件下提供。"""
    from .abstract import WavesCharRegister

    role_id = int(role_id)
    char_clz = WavesCharRegister.find_class(role_id)
    if char_clz is None:
        raise TeamConfigError(f"未找到角色【{role_id}】")
    if role_id not in supported_teammate_ids():
        raise TeamConfigError(f"【{getattr(char_clz, 'name', role_id)}】暂不支持作为自定义队友")

    instance = char_clz()
    func = _buff_callable(instance)

    effects: dict[tuple[str, str], dict] = {}
    combos: dict[str, set] = {}
    seen_category: set[str] = set()
    weapon_ids: list[int] = []
    total_combos = 0

    env_probes = _env_probes()
    attr_probes = _attr_probes()
    for chain in _CHAIN_PROBES:
        member = TeamMember(role_id=role_id, chain=chain, name=getattr(char_clz, "name", str(role_id)))
        kwargs = _buff_kwargs(func, member)
        for damage_type, damage_label in _damage_probes():
            for char_attr in attr_probes:
                for extra in env_probes:
                    total_combos += 1
                    attr = _scratch_attr(damage_type, char_attr, extra)
                    capture: dict[str, list[tuple[str, str]]] = {}
                    with _WeaponLookupRecorder() as recorder:
                        with _BuffFilter(attr, set(ALL_CATEGORIES), capture):
                            func(attr, **kwargs)
                    weapon_ids.extend(recorder.ids)

                    combo = (damage_label, char_attr, tuple(sorted(extra)))
                    for category, entries in capture.items():
                        if entries:
                            seen_category.add(category)
                        for title, msg in entries:
                            # 没有标题的是纯数值写入，同一段代码里的 add_effect 已经解释过它了
                            if not title:
                                continue
                            info = effects.setdefault(
                                (category, title),
                                {"category": category, "title": title, "msg": msg, "min_chain": chain, "count": 0},
                            )
                            if chain < info["min_chain"]:
                                info["min_chain"] = chain
                            info["count"] += 1
                            combos.setdefault(title, set()).add(combo)

    weapon_name = None
    if weapon_ids:
        weapon_clz = _weapon_class(weapon_ids[0])
        weapon_name = getattr(weapon_clz, "name", None) if weapon_clz else None

    declared = teammate_equip(role_id)
    declared_weapon = declared.get(KIND_WEAPON) or {}
    if declared_weapon.get("id"):
        weapon_name = weapon_name_of(declared_weapon["id"])
    elif KIND_WEAPON not in declared:
        # 角色本来就没写专武，不要凭空显示一把
        weapon_name = None
        weapon_ids = []

    equip = {
        "sonata": {"default": declared.get(KIND_SONATA), "options": preset_names(KIND_SONATA)},
        "echo": {"default": declared.get(KIND_ECHO), "options": preset_names(KIND_ECHO)},
        "weapon": {
            "default": weapon_name,
            "id": declared_weapon.get("id"),
            "declared": bool(declared_weapon),
            "options": [name for _id, name in weapon_options()],
        },
        # 条件套：满足条件时改带的那几套（默认值见上面的 default）
        "cases": equip_case_rows(declared),
    }

    categories: dict[str, dict] = {key: {"key": key, "label": label, "effects": []} for key, label in CATEGORY_LABELS.items()}
    damage_count = len(_damage_probes())
    for (category, _title), info in effects.items():
        if category not in categories:
            continue
        combo_set = combos.get(info["title"], set())
        categories[category]["effects"].append(
            {
                "title": info["title"],
                "msg": info["msg"],
                "min_chain": info["min_chain"],
                "condition": _condition_text(combo_set, total_combos, damage_count),
            }
        )
    for key, category in categories.items():
        category["effects"].sort(key=lambda item: (item["min_chain"], item["title"]))
        category["available"] = key in seen_category

    return {
        "role_id": role_id,
        "name": getattr(char_clz, "name", str(role_id)),
        "star_level": getattr(char_clz, "starLevel", None),
        "weapon_id": weapon_ids[0] if weapon_ids else None,
        "weapon_name": weapon_name,
        "equip": equip,
        "categories": [categories[key] for key in ALL_CATEGORIES],
        "states": [{"key": key, "hint": state_hint(role_id, key), **spec} for key, spec in teammate_states(role_id).items()],
    }


def weapon_name_of(weapon_id: int) -> str | None:
    weapon_clz = _weapon_class(weapon_id)
    return getattr(weapon_clz, "name", None) if weapon_clz else None


_TEMPLATE_LABELS = {temp_atk: "攻击", temp_life: "生命", temp_def: "防御"}


def equip_case_rows(declared: dict) -> list[dict]:
    """条件套的展示行：什么条件下换成什么（说明图直接用，不手写文案）。"""
    rows: list[dict] = []
    for case in declared_cases(declared):
        pieces = [f"{KIND_LABELS[kind]}={case[kind]}" for kind in EQUIP_KINDS if case.get(kind)]
        weapon = case.get(KIND_WEAPON)
        if isinstance(weapon, dict) and weapon.get("id"):
            pieces.append(f"{KIND_LABELS[KIND_WEAPON]}={weapon_name_of(weapon['id']) or weapon['id']}")
        rows.append({"when": case_condition_text(case), "equip": " / ".join(pieces)})
    return rows


def case_condition_text(case: dict) -> str:
    """条件套的条件渲染成人话，取值说明都取自现成的名字表。"""
    damages = dict(_damage_probes())
    parts: list[str] = []
    env = case.get(CASE_ENV)
    if env:
        parts.append(f"主角色处于{_env_labels().get(env, env)}")
    damage = case.get(CASE_DAMAGE)
    if damage:
        parts.append(f"主角色是{damages.get(damage, damage)}")
    template = case.get(CASE_TEMPLATE)
    if template:
        parts.append(f"主角色模板是{_TEMPLATE_LABELS.get(template, template)}")
    chain = case.get(CASE_CHAIN)
    if chain is not None:
        parts.append(f"自身{_format_state(chain)}链起")
    return "、".join(parts) or "无条件"


def _weapon_class(weapon_id: int):
    from .abstract import WavesWeaponRegister

    return WavesWeaponRegister.find_class(int(weapon_id))


def _condition_text(combo_set: set, total_combos: int, damage_count: int) -> str:
    """把探测到的生效范围压缩成一句人话；所有组合都命中就不显示条件。"""
    if not combo_set or len(combo_set) >= total_combos:
        return ""
    damages = {item[0] for item in combo_set}
    attrs = {item[1] for item in combo_set}
    envs = {item[2] for item in combo_set}
    env_off = () in envs
    parts = []
    if len(damages) < damage_count:
        parts.append("主角色" + "/".join(sorted(damages)))
    if len(attrs) < len(_attr_probes()):
        parts.append("主角色属性" + "/".join(sorted(attrs)))
    for key, label in _env_labels().items():
        if env_off:
            continue
        # 只要命中过「这个环境位开着」的组合，就说明这条增益需要它
        if any(key in combo for combo in envs):
            parts.append(label)
    return "；".join(parts)


def teammate_overview() -> list[dict]:
    """所有可作为自定义队友的角色一览（只读声明，不做昂贵探测）。

    同名条目（例如男女主角共用「漂泊者·气动」）按名字去重，保留 id 最小的那个，
    因为按名字查角色时也只会有唯一结果，列表里重复出现反而误导。
    """
    rows = {}
    for role_id in sorted(supported_teammate_ids()):
        char_clz = _char_registry().find_class(role_id)
        name = getattr(char_clz, "name", str(role_id))
        if name in rows:
            continue
        rows[name] = {
            "role_id": role_id,
            "name": name,
            "star_level": getattr(char_clz, "starLevel", None),
            "states": list(teammate_states(role_id)),
        }
    return sorted(rows.values(), key=lambda row: row["name"])


def example_commands(role_id: int, short_name: str = "") -> list[str]:
    name = short_name or char_name(role_id)
    commands = [f"ww心伤害3 换队友 {name}61", f"ww心伤害3 换队友 {name}01"]
    declared = teammate_equip(role_id)
    samples: list[str] = []
    other_sonata = next((x for x in preset_names(KIND_SONATA) if x != declared.get(KIND_SONATA)), None)
    if declared.get(KIND_SONATA) and other_sonata:
        samples.append(f"合鸣={other_sonata}")
    samples.append("延奏=关")
    commands.append(f"ww心伤害3 换队友 {name}01[{','.join(samples)}]")
    states = teammate_states(role_id)
    if states:
        state_samples = []
        for key, spec in states.items():
            if spec.get("type") == "bool":
                state_samples.append(f"{key}=关")
            elif spec.get("type") == "enum":
                choices = spec.get("choices", ())
                state_samples.append(f"{key}={choices[-1] if choices else ''}")
            else:
                low, high, default = spec.get("min"), spec.get("max"), spec.get("default")
                pick = low if default != low and low is not None else high
                state_samples.append(f"{key}={_format_state(pick)}")
        commands.append(f"ww心伤害3 换队友 {name}01[{','.join(state_samples)}]")
    return commands
