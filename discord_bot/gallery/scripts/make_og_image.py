"""Regenerate gallery OG image (1200x630) with clean official Shorekeeper pile art."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "img" / "og-image.jpg"
OUT_PNG = ROOT / "static" / "img" / "og-image.png"
SRC_DIR = Path(r"C:\Users\xu-ti\AppData\Local\Temp\ogfix")
PILE = SRC_DIR / "role_pile_1505.png"
AVATAR = SRC_DIR / "role_circle_head_1505.png"

W, H = 1200, 630
INK = (7, 19, 26)
FOAM = (231, 242, 244)
FOG = (158, 182, 194)
TIDE = (46, 196, 182)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
    return ImageFont.truetype(path, size=size, index=0)


def make_bg() -> Image.Image:
    """Near-uniform dark base + soft left glow only (no mid-frame color wall)."""
    img = Image.new("RGB", (W, H), INK)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((-160, -100, 480, 740), fill=(26, 143, 134, 32))
    glow = glow.filter(ImageFilter.GaussianBlur(100))
    return Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")


def place_character(canvas: Image.Image) -> None:
    """v=22 relative placement (right-heavy); soft alpha onto bg — no flat panel."""
    pile = Image.open(PILE).convert("RGBA")
    r, g, b, a = pile.split()
    a = a.point(lambda v: 0 if v < 12 else (v if v > 40 else int(v * ((v - 12) / 28))))
    pile = Image.merge("RGBA", (r, g, b, a))

    bbox = a.point(lambda v: 255 if v > 20 else 0).getbbox()
    if bbox:
        pad = 6
        l, t, rgt, btm = bbox
        pile = pile.crop(
            (
                max(0, l - pad),
                max(0, t - pad),
                min(pile.width, rgt + pad),
                min(pile.height, btm + pad),
            )
        )

    target_h = 680
    scale = target_h / pile.height
    pile = pile.resize(
        (max(1, int(pile.width * scale)), target_h),
        Image.Resampling.LANCZOS,
    )

    fade_w = 90
    a = pile.split()[-1]
    fade = Image.new("L", pile.size, 255)
    fpx = fade.load()
    for x in range(fade_w):
        av = int(255 * (x / fade_w) ** 1.3)
        for y in range(pile.height):
            fpx[x, y] = av
    pile.putalpha(Image.composite(a, Image.new("L", pile.size, 0), fade))

    # Anchor to right edge like v=22 (torso ~x800+).
    x = W - pile.width + 60
    y = H - pile.height + 20
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(pile, (x, y), pile)
    canvas.alpha_composite(layer)


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, ...],
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_text(canvas: Image.Image) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    badge = "鸣潮国际服 · Discord 机器人「守岸人」"
    bf = font(18)
    bb = draw.textbbox((0, 0), badge, font=bf)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    pad_x, pad_y = 16, 8
    bx, by = 56, 48
    rounded_rect(
        draw,
        (bx, by, bx + bw + pad_x * 2, by + bh + pad_y * 2),
        18,
        (255, 255, 255, 28),
    )
    draw.text((bx + pad_x, by + pad_y - 1), badge, font=bf, fill=(*FOAM, 230))

    title = "鸣潮机器人「守岸人」图集"
    tf = font(44, bold=True)
    draw.text((56, 100), title, font=tf, fill=(*FOAM, 255))

    sub = "角色面板立绘 · 自选背景图库 · 开放 API 增量同步"
    sf = font(20)
    draw.text((56, 164), sub, font=sf, fill=(*FOG, 230))

    # Divider matches v=22 copy width (stops before the figure).
    draw.line((56, 210, 560, 210), fill=(*TIDE, 140), width=2)

    bullets = [
        "严选 9:16 高清面板图，支持原图来源溯源与详情浏览",
        "Discord「守岸人」用户自选投稿，管理员多维度快速审核",
        "机器人端本地实时同步出图，并为第三方 Bot 提供 Manifest 接口",
    ]
    bf2 = font(18)
    y = 236
    for line in bullets:
        draw.ellipse((56, y + 8, 66, y + 18), fill=(*TIDE, 255))
        draw.text((78, y), line, font=bf2, fill=(*FOAM, 235))
        y += 42

    # Footer closer to bullets (shrink the empty mid-left band).
    foot_y = 388
    if AVATAR.is_file():
        av = Image.open(AVATAR).convert("RGBA").resize((44, 44), Image.Resampling.LANCZOS)
        mask = Image.new("L", (44, 44), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 44, 44), fill=255)
        av.putalpha(mask)
        layer.paste(av, (56, foot_y), av)

    ef = font(18, bold=True)
    uf = font(15)
    draw.text((112, foot_y), "Shorekeeper Panel Gallery", font=ef, fill=(*FOAM, 245))
    draw.text((112, foot_y + 26), "https://core.jotenbai.moe/gallery/", font=uf, fill=(*TIDE, 255))

    canvas.alpha_composite(layer)


def main() -> None:
    canvas = make_bg().convert("RGBA")
    place_character(canvas)
    draw_text(canvas)
    rgb = Image.new("RGB", (W, H), INK)
    rgb.paste(canvas, mask=canvas.split()[-1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rgb.save(OUT, "JPEG", quality=98, optimize=True, progressive=True, subsampling=0)
    canvas.convert("RGBA").save(OUT_PNG, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"wrote {OUT_PNG} ({OUT_PNG.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
