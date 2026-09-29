#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给漫画添加故事文字并合成为图文并茂的长图"""

import os
from PIL import Image, ImageDraw, ImageFont

# 设置路径
WORK_DIR = "/Users/zyb/WorkBuddy/automation-2026-05-13-task-2/云朵面包师"
SOURCE_IMG = os.path.join(WORK_DIR, "云朵面包师-漫画故事.png")
OUTPUT_IMG = os.path.join(WORK_DIR, "云朵面包师-图文漫画.png")

# 尝试加载字体
def get_font(size):
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()

# 故事文字（每格）
panel_texts = [
    "在白云上面，住着一个小面包师，\n他的名字叫朵朵。",
    "朵朵每天早上都会揉面团，\n烤出各种形状的面包——\n有月亮形的，有星星形的，\n还有太阳形的……",
    "有一天，风儿跑来告诉朵朵：\n山下的小动物们好久没\n吃到好吃的东西了！",
    "朵朵想了想，把刚烤好的\n面包一个一个放在云朵上，\n轻轻地推了出去……",
    "小鹿接到了月亮面包，\n小松鼠接到了星星面包，\n小刺猬接到了太阳面包，\n大家都开心地笑了！",
    "那天晚上，朵朵坐在云朵边上，\n望着亮亮的星星，\n心里比面包还要香甜。",
]

# 金句和标题
TITLE = "《云朵面包师》"
QUOTE = "💫 给小朋友的悄悄话：把爱放进每一个小礼物里，送出去的那一刻，你会比任何人都幸福。"

def add_text_to_comic():
    # 打开原图
    img = Image.open(SOURCE_IMG).convert("RGBA")
    w, h = img.size
    print(f"原图尺寸: {w}x{h}")

    num_panels = 6
    panel_height = h // num_panels
    text_height = 120  # 每格文字区域高度
    quote_height = 80   # 金句区域高度

    # 创建新画布（每格增加文字区域）
    new_h = h + num_panels * text_height + quote_height
    new_img = Image.new("RGBA", (w, new_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(new_img)

    # 添加标题
    title_font = get_font(48)
    title_bbox = draw.textbbox((0, 0), TITLE, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((w - title_w) // 2, 30), TITLE, fill=(80, 60, 120, 255), font=title_font)

    # 当前Y位置
    current_y = 0

    for i in range(num_panels):
        # 裁剪当前面板
        panel = img.crop((0, i * panel_height, w, (i + 1) * panel_height))

        # 粘贴面板
        new_img.paste(panel, (0, current_y))

        # 添加文字区域背景
        text_y = current_y + panel_height
        text_bg = Image.new("RGBA", (w, text_height), (245, 240, 255, 255))
        new_img.paste(text_bg, (0, text_y))

        # 添加文字
        text_font = get_font(26)
        text_content = panel_texts[i]
        lines = text_content.split("\n")
        line_h = 32
        total_text_h = len(lines) * line_h
        start_text_y = text_y + (text_height - total_text_h) // 2 - 5

        for j, line in enumerate(lines):
            draw.text((20, start_text_y + j * line_h), line,
                     fill=(60, 50, 90, 255), font=text_font)

        current_y = text_y + text_height

        print(f"第{i+1}格处理完成")

    # 添加金句区域
    quote_bg = Image.new("RGBA", (w, quote_height + 30), (230, 220, 250, 255))
    new_img.paste(quote_bg, (0, current_y))

    draw = ImageDraw.Draw(new_img)
    quote_font = get_font(24)
    quote_lines = [
        "✨ 给小朋友的悄悄话 ✨",
        "把爱放进每一个小礼物里，送出去的那一刻，你会比任何人都幸福。",
    ]
    for j, line in enumerate(quote_lines):
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        lw = bbox[2] - bbox[0]
        y_pos = current_y + 15 + j * 35
        if j == 0:
            draw.text(((w - lw) // 2, y_pos), line,
                     fill=(120, 80, 180, 255), font=quote_font)
        else:
            draw.text(((w - lw) // 2, y_pos), line,
                     fill=(80, 60, 120, 255), font=quote_font)

    # 保存
    new_img = new_img.convert("RGB")
    new_img.save(OUTPUT_IMG, "PNG", quality=95)
    print(f"\n✅ 图文漫画已保存: {OUTPUT_IMG}")

    # 输出尺寸
    final_w, final_h = new_img.size
    print(f"最终尺寸: {final_w}x{final_h}")

if __name__ == "__main__":
    add_text_to_comic()
