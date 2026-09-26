"""`ww队友配置` 说明图。

图里的内容全部来自 utils/damage/team.py 的自动探测 + 角色注册里声明的状态，
不手写死表：改了 _do_buff 或 teammate_states，说明图会自动跟着变。
"""

from PIL import Image, ImageDraw

from ..utils.damage.buff import CATEGORY_LABELS, TeamConfigError
from ..utils.damage.team import detect_teammate, example_commands, teammate_overview
from ..utils.fonts.waves_fonts import (
    waves_font_18,
    waves_font_20,
    waves_font_22,
    waves_font_24,
    waves_font_36,
)
from ..utils.image import GOLD, GREY, SPECIAL_GOLD, add_footer, draw_text_with_shadow, get_waves_bg

WIDTH = 1000
PADDING = 40
LINE = 30
WRAP = 44

_MARKERS = {"sonata": "合鸣效果-", "echo": "声骸技能-"}
_STATES_PER_ROW = 4  # 概览表每行至少列出 4 个状态，更多的用「等 N 项」收尾


class _Canvas:
    """按行往下画的简易画布，高度按实际行数算。"""

    def __init__(self, title: str, subtitle: str = ""):
        self.title = title
        self.subtitle = subtitle
        self._rows: list[tuple] = []

    def add(self, text: str, color=GREY, font=None, indent: int = 0):
        self._rows.append(("text", text, color, font or waves_font_20, indent))

    def add_columns(self, cells: list[tuple], font=None):
        """一行里按绝对 x 画多列，用来做真正对齐的表格。"""
        self._rows.append(("cols", tuple((text, color, x) for text, color, x in cells), font or waves_font_20))

    def gap(self, height: int = 12):
        self._rows.append(("gap", height))

    def header(self, text: str):
        self._rows.append(("text", text, SPECIAL_GOLD, waves_font_24, 0))

    def height(self) -> int:
        total = 140
        for row in self._rows:
            total += row[1] if row[0] == "gap" else LINE
        return total + 90

    def render(self) -> Image.Image:
        img = get_waves_bg(WIDTH, self.height(), "bg")
        draw = ImageDraw.Draw(img)
        draw_text_with_shadow(draw, self.title, PADDING, 44, waves_font_36, SPECIAL_GOLD, anchor="la")
        if self.subtitle:
            draw.text((PADDING, 92), self.subtitle, GOLD, waves_font_22)

        y = 140
        for row in self._rows:
            kind = row[0]
            if kind == "gap":
                y += row[1]
                continue
            if kind == "cols":
                cells, font = row[1], row[2]
                for text, color, x in cells:
                    if text:
                        draw.text((x, y), text, color, font)
                y += LINE
                continue
            _kind, text, color, font, indent = row
            if text:
                draw.text((PADDING + indent * 24, y), text, color, font)
            y += LINE
        add_footer(img)
        return img


def _wrap(text: str, limit: int = WRAP) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _stars(star) -> str:
    """星数只用于展示；注册数据里偶有 55 这种笔误，按上限5显示。"""
    try:
        count = int(star)
    except (TypeError, ValueError):
        return ""
    if count <= 0:
        return ""
    return "★" * min(count, 5)


def _preset_name(category: dict) -> str:
    """从探测到的标题里取出默认合鸣/声骸名字，例如 散华-合鸣效果-轻云出月 -> 轻云出月。"""
    marker = _MARKERS.get(category["key"])
    if not marker:
        return ""
    for effect in category["effects"]:
        title = effect["title"]
        if marker in title:
            return title.split(marker, 1)[1]
    return ""


def _category_line(category: dict) -> str:
    name = CATEGORY_LABELS.get(category["key"], category["key"])
    if not category["available"]:
        return f"{name}：该队友没有这部分增益"
    if category["key"] == "character":
        return f"{name}：开 / 关（总开关，关掉后该队友不提供任何增益）"
    preset = _preset_name(category)
    preset_text = f"（默认 {preset}）" if preset else ""
    return f"{name}：开 / 关{preset_text}"


def build_teammate_canvas(config: dict, short_name: str = "") -> _Canvas:
    name = config["name"]
    canvas = _Canvas(f"队友配置 · {name}", f"{_stars(config.get('star_level'))}    只影响本次伤害模拟，不写面板、不参与排名")

    canvas.header("一、可以开关的部分")
    for category in config["categories"]:
        canvas.add(_category_line(category), GREY, waves_font_22)
        for effect in category["effects"]:
            chain_tag = f"[{effect['min_chain']}链起] " if effect["min_chain"] > 0 else ""
            canvas.add(f"{chain_tag}{effect['title']}", GOLD, waves_font_20, 1)
            for line in _wrap(effect["msg"]):
                canvas.add(line, GREY, waves_font_18, 2)
            if effect["condition"]:
                canvas.add(f"（{effect['condition']}）", SPECIAL_GOLD, waves_font_18, 2)
    weapon_name = config.get("weapon_name")
    if weapon_name:
        canvas.add(f"专武：开 / 关（默认 {weapon_name}，按武器精炼计算）", GREY, waves_font_22)
    else:
        canvas.add("专武：该队友的增益不依赖专武，开关不生效", GREY, waves_font_22)

    canvas.gap()
    canvas.header("二、可以换的装备")
    canvas.add("任何队友都能自己指定套装/声骸/武器，和角色本身有没有写无关", GREY, waves_font_20)
    equip = config.get("equip") or {}
    _add_equip_rows(canvas, "合鸣效果", "合鸣", equip.get("sonata"))
    _add_equip_rows(canvas, "声骸技能", "声骸", equip.get("echo"))
    _add_weapon_rows(canvas, equip.get("weapon") or {})
    for case in equip.get("cases") or []:
        canvas.add(f"满足条件时改带另一套 —— {case['when']}：{case['equip']}", SPECIAL_GOLD, waves_font_18, 2)

    canvas.gap()
    canvas.header("三、可以调整的状态")
    if config["states"]:
        for spec in config["states"]:
            canvas.add(f"{spec['key']}　{spec['hint']}", GOLD, waves_font_22)
            for line in _wrap(spec.get("desc", "")):
                canvas.add(line, GREY, waves_font_18, 2)
        canvas.add("写法：队友名后面接 [状态=值]，多个用逗号分隔", GREY, waves_font_18, 1)
    else:
        canvas.add(f"{name} 没有可调状态，只支持共鸣链、专武精炼和上面的开关", GREY, waves_font_20)

    canvas.gap()
    canvas.header("四、指令示例")
    for command in example_commands(config["role_id"], short_name):
        canvas.add(command, GOLD, waves_font_20, 1)

    return canvas


def _add_equip_rows(canvas: _Canvas, label: str, key: str, info: dict | None) -> None:
    """合鸣/声骸：这个队友默认用哪套、还能换成哪些（任何角色都能自己指定）。"""
    if not info:
        return
    default = info.get("default")
    if default:
        canvas.add(f"{label}：默认 {default}", GOLD, waves_font_22)
    else:
        canvas.add(f"{label}：默认不带（该角色原本没有写这部分）", GOLD, waves_font_22)
    options = [name for name in info.get("options", []) if name != default]
    if options:
        for line in _wrap(f"可以填：{' / '.join(options)}", WRAP):
            canvas.add(line, GREY, waves_font_18, 2)
    canvas.add(f"写法：{key}=名称 换一套，{key}=关 不算这部分", GREY, waves_font_18, 2)


def _add_weapon_rows(canvas: _Canvas, info: dict) -> None:
    if info.get("default"):
        canvas.add(f"专武：默认 {info['default']}", GOLD, waves_font_22)
    else:
        canvas.add("专武：默认不带（该角色原本没有专武增益）", GOLD, waves_font_22)
    options = info.get("options") or []
    if options:
        for line in _wrap(f"可以填：{' / '.join(options)}", WRAP):
            canvas.add(line, GREY, waves_font_18, 2)
    canvas.add("写法：武器=关 不算专武，也可以填上面任意一把武器名", GREY, waves_font_18, 2)


async def draw_teammate_config_img(role_id: int, short_name: str = "") -> Image.Image | str:
    try:
        config = detect_teammate(role_id)
    except TeamConfigError as e:
        return f"[鸣潮] 队友配置错误：{e}\n"
    return build_teammate_canvas(config, short_name).render()


def _states_cell(states: list[str]) -> str:
    """概览表每行列出至多 4 个可调状态，更多的用「等 N 项」收尾。"""
    if not states:
        return "—"
    if len(states) <= _STATES_PER_ROW:
        return "、".join(states)
    shown = "、".join(states[:_STATES_PER_ROW])
    return f"{shown} 等 {len(states)} 项"


def build_overview_canvas() -> _Canvas:
    rows = teammate_overview()
    canvas = _Canvas("队友配置一览", f"共 {len(rows)} 名角色可作为自定义队友；发送 ww队友配置角色名 看详细说明")

    header = ("角色", "星级", "可调状态[方括号包裹]")
    table = [(row["name"], _stars(row.get("star_level")) or "—", _states_cell(row["states"])) for row in rows]
    # 列位置按实际文字宽度算：中文宽度不固定，写死 x 会对不齐
    header_font, body_font = waves_font_22, waves_font_20
    widths = [max(header_font.getlength(line[index]) for line in (header, *table)) for index in range(len(header))]
    xs: list[int] = []
    cursor = float(PADDING)
    for width in widths:
        xs.append(int(cursor))
        cursor += width + 48

    canvas.add_columns([(header[i], SPECIAL_GOLD, xs[i]) for i in range(len(header))], header_font)
    for name, stars, states in table:
        canvas.add_columns([(name, GREY, xs[0]), (stars, GOLD, xs[1]), (states, GREY, xs[2])], body_font)
    canvas.gap()
    canvas.add("每行最多列 4 个状态，完整列表、默认值和生效条件以 ww队友配置角色名 的说明为准", GOLD, waves_font_18, 1)
    return canvas


async def draw_teammate_overview_img() -> Image.Image:
    return build_overview_canvas().render()


def config_as_text(config: dict) -> list[str]:
    """纯文本版说明，便于测试与不支持图片的适配器。"""
    lines = [f"队友配置 · {config['name']}"]
    for category in config["categories"]:
        lines.append(_category_line(category))
        for effect in category["effects"]:
            chain_tag = f"[{effect['min_chain']}链起] " if effect["min_chain"] > 0 else ""
            condition = f"（{effect['condition']}）" if effect["condition"] else ""
            lines.append(f"  {chain_tag}{effect['title']}：{effect['msg']}{condition}")
    if config.get("weapon_name"):
        lines.append(f"专武：默认 {config['weapon_name']}")
    for case in (config.get("equip") or {}).get("cases") or []:
        lines.append(f"条件套：{case['when']} → {case['equip']}")
    for spec in config["states"]:
        lines.append(f"状态 {spec['key']}　{spec['hint']}　{spec.get('desc', '')}")
    return lines
