import os
from pathlib import Path

import numpy as np
from PIL import Image

from ..utils.resource.RESOURCE_PATH import CIRCLE_AVATAR_PATH, MATRIX_PATH
from .match_core import (
    compare_slot,
    pil_to_rgb_on_black,
    rgb_to_luma_np_uint8,
)

# PATH for Resonator & buff icon image data
ROUND_AVATAR_PATH = str(CIRCLE_AVATAR_PATH)

# BUFF ICON
BUFF_ICON_PATH = str(MATRIX_PATH)

# PATH for numbers
NUMBER_PATH = str(Path(__file__).parent / "number_images")

# 空位检测: 圆内 luma 标准差低于此值视为空位
EMPTY_INNER_STD_THRESHOLD = 25

# 未检出分隔线时按行高推算其横坐标 (1920x1080 实测 405/91)
GRAY_BAR_RATIO = 4.45

# 数字模板匹配参数
NUMBER_COMPARE_SIZE = (32, 43)

# arrays for data
number_files = sorted([f for f in os.listdir(NUMBER_PATH) if f.lower().endswith(".png")])
num_data = []

image_files = sorted([f for f in os.listdir(ROUND_AVATAR_PATH) if f.lower().endswith(".png")])
img_data = []

# buff 图标在运行中可能被补下载, 由 init() 每次重新扫描目录
buff_imgs: list[str] = []
buff_data = []


#
# Extract team blocks
#
def is_valid_color(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    diff = max_val - min_val
    if max_val == min_val:
        h = 0.0
    elif max_val == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif max_val == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    elif max_val == b:
        h = (60 * ((r - g) / diff) + 240) % 360
    if max_val == 0:
        s = 0.0
    else:
        s = (diff / max_val) * 100
    v = max_val * 100
    return 195 < h < 215 and 17 < s < 30 and 25 < v < 40


def get_valid_blocks(img, min_pixel_size=5000):
    width, height = img.size
    pixels = img.load()
    visited = set()
    blocks = []
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (0, 2), (0, -2), (2, 0), (-2, 0), (0, 3), (0, -3), (3, 0), (-3, 0)]
    for y in range(height):
        for x in range(width):
            if (x, y) in visited:
                continue
            r, g, b = pixels[x, y]
            if is_valid_color(r, g, b):
                block_pixels = []
                queue = [(x, y)]
                visited.add((x, y))
                while queue:
                    curr_x, curr_y = queue.pop(0)
                    block_pixels.append((curr_x, curr_y))
                    for dx, dy in directions:
                        nx, ny = curr_x + dx, curr_y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            if (nx, ny) not in visited:
                                nr, ng, nb = pixels[nx, ny]
                                if is_valid_color(nr, ng, nb):
                                    visited.add((nx, ny))
                                    queue.append((nx, ny))
                if len(block_pixels) >= min_pixel_size:
                    xs = [p[0] for p in block_pixels]
                    ys = [p[1] for p in block_pixels]
                    bbox = (min(xs), min(ys), max(xs), max(ys))
                    blocks.append({"pixel_count": len(block_pixels), "bbox": bbox, "pixels": block_pixels})

    # Merge blocks that are close or next to each other
    used = np.full(len(blocks), [False])
    res = []
    heights = []

    for i, iblock in enumerate(blocks):
        if used[i]:
            continue
        x0, y0, x1, y1 = iblock["bbox"][0], iblock["bbox"][1], iblock["bbox"][2], iblock["bbox"][3]
        used[i] = True
        res_curr = iblock
        heights.append(y1 - y0)

        for j, jblock in enumerate(blocks):
            if used[j]:
                continue
            xx0, yy0, xx1, yy1 = jblock["bbox"][0], jblock["bbox"][1], jblock["bbox"][2], jblock["bbox"][3]
            if abs(y0 - yy0) <= 3 and abs(y1 - yy1) <= 3 and (abs(x1 - xx0) <= 5 or x1 > xx0):
                res_curr["pixel_count"] = res_curr["pixel_count"] + jblock["pixel_count"]
                res_curr["bbox"] = (min(x0, xx0), y0, max(x1, xx1), y1)
                x0, y0, x1, y1 = res_curr["bbox"][0], res_curr["bbox"][1], res_curr["bbox"][2], res_curr["bbox"][3]
                used[j] = True

        res.append(res_curr)

    # Height < most common, increase bbox from top / bottom based on position
    most_common_height = max(set(heights), key=heights.count)
    count = 0
    for num in heights:
        if num == most_common_height:
            count = count + 1
    if count == 1:
        most_common_height = int(np.median(heights) + 0.5)

    for i, height in enumerate(heights):
        if height < most_common_height and most_common_height - height >= 2:
            if res[i]["bbox"][1] < img.size[1] // 2:
                res[i]["bbox"] = [
                    res[i]["bbox"][0],
                    max(0, res[i]["bbox"][1] - most_common_height + height),
                    res[i]["bbox"][2],
                    res[i]["bbox"][3],
                ]
            else:
                res[i]["bbox"] = [
                    res[i]["bbox"][0],
                    res[i]["bbox"][1],
                    res[i]["bbox"][2],
                    min(img.size[1], res[i]["bbox"][3] + most_common_height - height),
                ]

    return res


def to_hsv(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    diff = max_val - min_val
    if max_val == min_val:
        h = 0.0
    elif max_val == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif max_val == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    elif max_val == b:
        h = (60 * ((r - g) / diff) + 240) % 360
    if max_val == 0:
        s = 0.0
    else:
        s = (diff / max_val) * 100
    v = max_val * 100
    return h, s, v


def _mask_outside_circle(img: Image.Image, radius_ratio: float = 0.92) -> Image.Image:
    """圆形头像外侧 (灰底+边框) 涂黑, 与黑底模板对齐, 避免背景色主导颜色相似度."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    outside = ((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2 > radius_ratio**2
    arr[outside] = 0
    return Image.fromarray(arr)


def _crop_to_circle(img: Image.Image, diff_thr: int = 30) -> Image.Image:
    """按与四角背景色的差异找出头像圆的外接框并裁切, 使圆与模板等大对齐."""
    arr = np.array(img).astype(np.int32)
    h, w = arr.shape[:2]
    k = max(2, min(h, w) // 15)
    corners = np.concatenate(
        [arr[:k, :k].reshape(-1, 3), arr[:k, -k:].reshape(-1, 3), arr[-k:, :k].reshape(-1, 3), arr[-k:, -k:].reshape(-1, 3)]
    )
    bg = np.median(corners, axis=0)
    fg = np.abs(arr - bg).max(axis=2) > diff_thr
    rows = np.where(fg.sum(axis=1) > w // 20)[0]
    cols = np.where(fg.sum(axis=0) > h // 20)[0]
    if len(rows) == 0 or len(cols) == 0:
        return img
    x0, x1, y0, y1 = cols[0], cols[-1] + 1, rows[0], rows[-1] + 1
    if (x1 - x0) < w * 0.6 or (y1 - y0) < h * 0.6:
        return img
    return img.crop((int(x0), int(y0), int(x1), int(y1)))


def _inner_luma_std(img: Image.Image, radius_ratio: float = 0.75) -> float:
    arr = np.array(img).astype(np.float64)
    luma = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
    h, w = luma.shape
    yy, xx = np.ogrid[:h, :w]
    inside = ((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2 <= radius_ratio**2
    return float(luma[inside].std())


def init(force: bool = False) -> None:
    if not force and num_data and img_data and buff_data:
        return
    num_data.clear()
    img_data.clear()
    buff_data.clear()
    # Read number templates
    for img_name in number_files:
        img_ava = Image.open(os.path.join(NUMBER_PATH, img_name))
        rgb = pil_to_rgb_on_black(img_ava).resize(NUMBER_COMPARE_SIZE, Image.Resampling.LANCZOS)
        arr = np.array(rgb)
        luma_np = rgb_to_luma_np_uint8(rgb)
        mean_rgb = arr.reshape(-1, 3).mean(axis=0).astype(np.float64)
        num_data.append((rgb, luma_np, mean_rgb))

    # Read resonator icons
    for img_name in image_files:
        img_ava = Image.open(os.path.join(ROUND_AVATAR_PATH, img_name))
        rgb = pil_to_rgb_on_black(img_ava).resize((128, 128), Image.Resampling.LANCZOS)
        rgb = _mask_outside_circle(Image.fromarray(np.array(rgb)[2:124, 0:127]))
        arr = np.array(rgb)
        luma_np = rgb_to_luma_np_uint8(rgb)
        mean_rgb = arr.reshape(-1, 3).mean(axis=0).astype(np.float64)
        img_data.append((rgb, luma_np, mean_rgb))

    # Read BUFF icons
    # 同目录还存有 boss 立绘等大图, 只取近似正方形的小图标
    buff_imgs.clear()
    names = sorted(f for f in os.listdir(BUFF_ICON_PATH) if f.lower().endswith(".png")) if os.path.isdir(BUFF_ICON_PATH) else []
    for img_name in names:
        img_ava = Image.open(os.path.join(BUFF_ICON_PATH, img_name))
        w, h = img_ava.size
        if abs(w - h) > max(w, h) * 0.1 or max(w, h) > 512:
            continue
        buff_imgs.append(img_name)
        rgb = pil_to_rgb_on_black(img_ava).resize((75, 75), Image.Resampling.LANCZOS)
        arr = np.array(rgb)
        luma_np = rgb_to_luma_np_uint8(rgb)
        mean_rgb = arr.reshape(-1, 3).mean(axis=0).astype(np.float64)
        buff_data.append((rgb, luma_np, mean_rgb))


def ReadMatrixImg(Matrix_Img_PATH):
    """原脚本主入口. 输入支持路径或 PIL.Image."""
    if isinstance(Matrix_Img_PATH, (str, Path)):
        img = Image.open(Matrix_Img_PATH).convert("RGB")
    else:
        img = Matrix_Img_PATH.convert("RGB") if Matrix_Img_PATH.mode != "RGB" else Matrix_Img_PATH

    hsv_img = img.convert("HSV")
    hsv_data = np.array(hsv_img)
    rgb_data = np.array(img)

    # Light gray -> gray
    lower = np.array([203 * 255 / 360, 21 * 255 / 100, 48 * 255 / 100])
    upper = np.array([207 * 255 / 360, 25 * 255 / 100, 52 * 255 / 100])
    mask = np.all((hsv_data >= lower) & (hsv_data <= upper), axis=-1)
    rgb_data[mask] = np.array([61, 72, 80])
    img = Image.fromarray(rgb_data)

    res = get_valid_blocks(img)

    res_img = []

    for index, one_team in enumerate(res):
        team_to_test = np.array(img)[res[index]["bbox"][1] : res[index]["bbox"][3], res[index]["bbox"][0] : res[index]["bbox"][2]]

        h_block = team_to_test.shape[0]
        # remove blocks that are not valid / change constant parameters
        if team_to_test.shape[1] < img.size[0] // 3:
            continue

        # team number 完全由 OCR 识别, 不再做数字模板匹配
        res_numbers = 0

        # Identify resonator
        start_pos = [159 * h_block // 122, 0]

        grayBar_pos = 0

        # Locate the bar right next to 3 resonators
        # 队伍栏半透明, 分隔线色相随背后画面在 ~200-215 间浮动, 上限放宽到 220
        for i in range(start_pos[0], min(h_block * 5, team_to_test.shape[1])):
            count = 0
            for j in range(0, h_block):
                pixel_rgb = team_to_test[j][i]
                h, s, v = to_hsv(pixel_rgb[0], pixel_rgb[1], pixel_rgb[2])
                if 198 < h < 220 and 5 < s < 15 and 40 < v < 60:
                    count = count + 1
            if count > h_block // 4:
                grayBar_pos = i
                break
        if grayBar_pos == 0:
            grayBar_pos = int(h_block * GRAY_BAR_RATIO)

        area_w, area_h = 366 * h_block // 122, h_block

        three_resonator_block = team_to_test[
            start_pos[1] : start_pos[1] + area_h, start_pos[0] : grayBar_pos - int(h_block * 0.1)
        ]

        # Divide to 3 resonators
        avatar_w = three_resonator_block.shape[1] // 3

        resonator_in_team = []

        for i in range(3):
            sub_image = three_resonator_block[0 : three_resonator_block.shape[0], avatar_w * i : avatar_w * (i + 1)]
            resonator_in_team.append(sub_image)

        # Compare each resonator w/ database
        AVATAR_COMPARE_SIZE = (127, 122)

        res_resonator = []

        for i, resonator_avatar in enumerate(resonator_in_team):
            ava_img = Image.fromarray(resonator_avatar)

            plain = ava_img.resize(AVATAR_COMPARE_SIZE, Image.Resampling.LANCZOS)

            # 空位检测: 只看圆内亮度标准差 (空位为灰底剪影 ~14, 真实头像 >35), 外圈边框/背景不参与
            if _inner_luma_std(plain) < EMPTY_INNER_STD_THRESHOLD:
                res_resonator.append("empty.webp")
                continue

            # 切图中圆的位置/大小随行而异, 原切图与按圆裁切两种候选取高分
            variants = [
                _mask_outside_circle(plain),
                _mask_outside_circle(_crop_to_circle(ava_img).resize(AVATAR_COMPARE_SIZE, Image.Resampling.LANCZOS)),
            ]

            best_score = -1.0
            best_idx = 0
            for idx, tpl in enumerate(img_data):
                final = max(compare_slot(v, tpl, AVATAR_COMPARE_SIZE)[0] for v in variants)
                if final > best_score:
                    best_score = final
                    best_idx = idx

            res_resonator.append(image_files[best_idx])

        # Identify BUFF
        buff_x0 = grayBar_pos + 27 * h_block // 122

        buff_w, buff_h = 75 * h_block // 122, 75 * h_block // 122

        buff_icon = team_to_test[(h_block - buff_h) // 2 : (h_block + buff_h) // 2, buff_x0 : buff_x0 + buff_w]

        BUFF_COMPARE_SIZE = (75, 75)

        buff_img = Image.fromarray(buff_icon)

        buff_arr = np.array(buff_img.resize(BUFF_COMPARE_SIZE, Image.Resampling.LANCZOS))

        best_score = -1.0
        best_idx = 0
        for idx, tpl in enumerate(buff_data):
            final, _, _, _ = compare_slot(buff_img, tpl, BUFF_COMPARE_SIZE)
            if final > best_score:
                best_score = final
                best_idx = idx

        # Bounding box for wave info & score
        # team number 区域 (合并十位+个位), 供 processor 裁切 OCR
        team_number_area = [
            res[index]["bbox"][0] + 33 * h_block // 118,
            res[index]["bbox"][1] + h_block // 2 - 21 * h_block // 118,
            65 * h_block // 118,
            45 * h_block // 118,
        ]
        wave_number = [
            res[index]["bbox"][0] + (grayBar_pos + team_to_test.shape[1]) // 2 - int(h_block * 1.2),
            res[index]["bbox"][1] + h_block // 6,
            int(h_block * 1.2),
            h_block // 3,
        ]
        monster_count = [
            res[index]["bbox"][0] + (grayBar_pos + team_to_test.shape[1]) // 2 - h_block * 2 // 3,
            res[index]["bbox"][1] + h_block // 2,
            h_block * 2 // 3,
            h_block // 2,
        ]
        team_score = [
            res[index]["bbox"][0] + team_to_test.shape[1] - int(h_block * 2),
            res[index]["bbox"][1] + h_block // 3,
            int(h_block * 2),
            h_block // 3,
        ]

        # 空队伍也返回, 标记 is_empty, 由调用方决定是否覆盖本地数据
        is_empty = "empty.webp" in res_resonator
        res_img.append(
            {
                "Team #": res_numbers,
                "Resonators": res_resonator,
                "BUFF": buff_imgs[best_idx] if buff_imgs else "",
                "Team Number Area": team_number_area,
                "Wave Number Area": wave_number,
                "Monster Count Area": monster_count,
                "Team Score Area": team_score,
                "is_empty": is_empty,
            }
        )

    return res_img


def match_team_number(pil_img: Image.Image, h_block: int) -> int:
    """数字模板匹配 team number. 输入 team number 区域的裁切图, 返回两位数."""
    num_img = pil_img.resize(NUMBER_COMPARE_SIZE, Image.Resampling.LANCZOS)
    best_score = -1.0
    best_idx = 0
    for idx, tpl in enumerate(num_data):
        final, _, _, _ = compare_slot(num_img, tpl, NUMBER_COMPARE_SIZE)
        if final > best_score:
            best_score = final
            best_idx = idx
    return int(number_files[best_idx].split(".")[0])


# wwuid 兼容别名
read_matrix_image = ReadMatrixImg
