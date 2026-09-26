from ...utils.damage.damage import DamageAttribute


class WavesRegister:
    _id_cls_map = {}

    @classmethod
    def find_class(cls, _id):
        return cls._id_cls_map.get(_id)

    @classmethod
    def register_class(cls, _id, _clz):
        # old_cls = cls.find_class(_id)
        # if old_cls:
        #     raise TypeError('%s already register %s for type %s' % (cls, old_cls, _id))
        cls._id_cls_map[_id] = _clz


class WavesWeaponRegister(WavesRegister):
    _id_cls_map = {}


class WavesEchoRegister(WavesRegister):
    _id_cls_map = {}


class WavesCharRegister(WavesRegister):
    _id_cls_map = {}


class DamageDetailRegister(WavesRegister):
    _id_cls_map = {}


class DamageRankRegister(WavesRegister):
    _id_cls_map = {}


class WeaponAbstract:
    id = None
    type = None
    name = None

    def __init__(
        self,
        weapon_id: str | int,
        weapon_level: int,
        weapon_breach: int | None = None,
        weapon_reson_level: int = 1,
    ):
        from ...utils.ascension.weapon import (
            WavesWeaponResult,
            get_weapon_detail,
        )

        weapon_detail: WavesWeaponResult = get_weapon_detail(weapon_id, weapon_level, weapon_breach, weapon_reson_level)
        self.weapon_id = weapon_id
        self.weapon_level = weapon_level
        self.weapon_breach = weapon_breach
        self.weapon_reson_level = weapon_reson_level
        self.weapon_detail: WavesWeaponResult = weapon_detail

    def do_action(
        self,
        func_list: list[str] | str,
        attr: DamageAttribute,
        isGroup: bool = False,
    ):
        if isinstance(func_list, str):
            func_list = [func_list]

        if isGroup:
            func_list.append("cast_variation")

        if attr.env_spectro:
            func_list.append("env_spectro")

        if attr.env_aero_erosion:
            func_list.append("env_aero_erosion")

        if attr.env_havoc_bane:
            func_list.append("env_havoc_bane")

        if attr.env_fusion_burst:
            func_list.append("env_fusion_burst")

        if attr.env_glacio_chafe:
            func_list.append("env_glacio_chafe")

        if attr.env_electro_flare:
            func_list.append("env_electro_flare")

        if attr.trigger_shield:
            func_list.append("trigger_shield")

        func_list.append("cast_phantom")

        func_list.append("cast_tune_break")

        func_list = [x for i, x in enumerate(func_list) if func_list.index(x) == i]

        for func_name in func_list:
            method = getattr(self, func_name, None)
            if callable(method):
                if method(attr, isGroup):
                    return

    def get_title(self):
        return f"{self.name}-{self.weapon_detail.get_resonLevel_name()}"

    def param(self, param):
        return self.weapon_detail.param[param][self.weapon_reson_level - 1]

    def buff(self, attr: DamageAttribute, isGroup: bool = False):
        """buff"""
        pass

    def damage(self, attr: DamageAttribute, isGroup: bool = False):
        """造成伤害"""
        pass

    def cast_attack(self, attr: DamageAttribute, isGroup: bool = False):
        """施放普攻"""
        pass

    def cast_hit(self, attr: DamageAttribute, isGroup: bool = False):
        """施放重击"""
        pass

    def cast_skill(self, attr: DamageAttribute, isGroup: bool = False):
        """施放共鸣技能"""
        pass

    def cast_liberation(self, attr: DamageAttribute, isGroup: bool = False):
        """施放共鸣解放"""
        pass

    def cast_phantom(self, attr: DamageAttribute, isGroup: bool = False):
        """施放声骸技能"""
        pass

    def cast_dodge_counter(self, attr: DamageAttribute, isGroup: bool = False):
        """施放闪避反击"""
        pass

    def cast_variation(self, attr: DamageAttribute, isGroup: bool = False):
        """施放变奏技能"""
        pass

    def skill_create_healing(self, attr: DamageAttribute, isGroup: bool = False):
        """共鸣技能造成治疗"""
        pass

    def env_spectro(self, attr: DamageAttribute, isGroup: bool = False):
        """光噪效应"""
        pass

    def env_aero_erosion(self, attr: DamageAttribute, isGroup: bool = False):
        """风蚀效应"""
        pass

    def env_havoc_bane(self, attr: DamageAttribute, isGroup: bool = False):
        """虚湮效应"""
        pass

    def env_fusion_burst(self, attr: DamageAttribute, isGroup: bool = False):
        """聚爆效应"""
        pass

    def env_glacio_chafe(self, attr: DamageAttribute, isGroup: bool = False):
        """霜渐效应"""
        pass

    def env_electro_flare(self, attr: DamageAttribute, isGroup: bool = False):
        """电磁效应"""
        pass

    def trigger_shield(self, attr: DamageAttribute, isGroup: bool = False):
        """触发护盾"""
        pass

    def cast_tune_break(self, attr: DamageAttribute, isGroup: bool = False):
        """施放谐度破坏技"""
        pass

    def cast_healing(self, attr: DamageAttribute, isGroup: bool = False):
        """施放治疗"""
        pass

    def cast_extension(self, attr: DamageAttribute, isGroup: bool = False):
        """施放延奏技能"""
        pass


class EchoAbstract:
    name = None
    id = None

    def do_echo(self, attr: DamageAttribute, isGroup: bool = False):
        self.damage(attr, isGroup)

    def damage(self, attr: DamageAttribute, isGroup: bool = False):
        """造成伤害"""
        pass

    def do_equipment_first(self, role_id: int):
        """首位装备"""
        return {}


class CharAbstract:
    name = None
    id: int | None = None
    starLevel = None

    # 作为「自定义队友」时用户可以调整的状态，按需在子类声明。
    #
    # 写法（键就是用户输入的参数名）::
    #
    #     teammate_states = {
    #         "祝福层数": {
    #             "type": "int",        # int / bool / enum
    #             "min": 0,             # int 必填
    #             "max": 10,            # int 必填
    #             "default": 10,        # 不写时按原实现里的默认假设
    #             "desc": "每层全伤害加深4%",
    #         },
    #         "领域": {"type": "bool", "default": True, "desc": "..."},
    #         "模式": {"type": "enum", "choices": ("告解", "赦罪"), "default": "告解", "desc": "..."},
    #     }
    #
    # 声明后：校验、解析、`ww队友配置` 说明图都由这份声明生成，
    # 且 _do_buff 里必须真的读取 states，否则默认值不会变。
    teammate_states: dict[str, dict] = {}

    # 作为「自定义队友」时的默认装备，按需在子类声明。
    #
    # 写法（键就是装备目录里的分类名）::
    #
    #     teammate_equip = {
    #         "sonata": "轻云出月",  # 默认合鸣，取值见 buff.SONATA_PRESETS
    #         "echo": "无常凶鹭",  # 默认声骸，取值见 buff.ECHO_PRESETS
    #         "weapon": {"id": 21050036, "action": "skill_create_healing"},  # 默认专武 + 用哪个行为触发
    #     }
    #
    # 每个键都是「这个角色本来就有这一部分」的意思：写了才会作为默认值施加，
    # 也才能被指令覆盖（`合鸣=…` / `声骸=…` / `武器=…`，填「关」表示这次不带）。
    # 没写的键表示角色本来就不带这一部分，此时任何预设都可以由指令直接指定。
    #
    # 数值和生效条件只在 buff.py 的目录里维护一份：这里只写「用哪一套」，
    # 具体给多少、什么条件下给（例如只在主C为某属性时给）都写在预设的 apply 里，
    # 所以 _do_buff 里不要再把同一套合鸣 / 声骸写第二遍。
    teammate_equip: dict = {}

    def do_buff(
        self,
        attr: DamageAttribute,
        chain: int = 0,
        resonLevel: int = 1,
        isGroup: bool = True,
    ):
        """
        获得buff

        :param attr: 人物伤害属性
        :param chain: 命座
        :param resonLevel: 武器谐振
        :param isGroup: 是否组队

        """
        attr.add_teammate(self.id)
        self._do_buff(attr, chain, resonLevel, isGroup)

    def _do_buff(
        self,
        attr: DamageAttribute,
        chain: int = 0,
        resonLevel: int = 1,
        isGroup: bool = True,
    ):
        """
        获得buff

        :param attr: 人物伤害属性
        :param chain: 命座
        :param resonLevel: 武器谐振
        :param isGroup: 是否组队

        """
        pass
