"""Assemble the review renders into one labelled contact sheet.

    python3 make_sheet.py <render_dir> <out.png> [--tile 420]
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
tile = int(sys.argv[sys.argv.index("--tile") + 1]) if "--tile" in sys.argv else 420
LABELS = [
    ("01_front34", "FRONT 3/4"), ("02_front", "FRONT"), ("03_side", "SIDE"), ("04_back", "BACK"),
    ("05_torso_close", "TORSO / LAPELS / SASH"), ("05b_torso_side", "TORSO SIDE"),
    ("06_hair_close", "HAIR CLOSE-UP"), ("06b_face_close", "FACE CLOSE-UP"),
    ("07_silhouette_front", "SILHOUETTE FRONT"), ("07b_silhouette_side", "SILHOUETTE SIDE"),
    ("07c_silhouette_34", "SILHOUETTE 3/4"), ("08_arms45", "ARMS 45°"),
    ("09_arms90", "ARMS 90°"), ("09b_arms90_back", "ARMS 90° BACK"),
    ("10_armraise", "ONE ARM RAISED"), ("11_torso_twist", "TORSO TWIST 22°"),
]
items = [(f, l) for f, l in LABELS if os.path.exists(os.path.join(src, f + ".png"))]
cols = 4
rows = (len(items) + cols - 1) // cols
pad, lab = 10, 34
W = cols * tile + (cols + 1) * pad
H = rows * (tile + lab) + (rows + 1) * pad + 50
sheet = Image.new("RGB", (W, H), (22, 23, 27))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except OSError:
    font = big = ImageFont.load_default()
d.text((pad + 4, 12), "HEALER / BRAWLER UNIT — R15 FOUNDATION + CUSTOM ANIME GEOMETRY — REVIEW SHEET",
       fill=(235, 235, 240), font=big)
for i, (f, l) in enumerate(items):
    im = Image.open(os.path.join(src, f + ".png")).convert("RGB")
    im.thumbnail((tile, tile), Image.LANCZOS)
    r, c = divmod(i, cols)
    x0 = pad + c * (tile + pad)
    y0 = 50 + pad + r * (tile + lab + pad)
    d.rectangle([x0, y0, x0 + tile, y0 + tile], fill=(40, 42, 48))
    sheet.paste(im, (x0 + (tile - im.width) // 2, y0 + (tile - im.height) // 2))
    tw = d.textlength(l, font=font)
    d.text((x0 + (tile - tw) / 2, y0 + tile + 7), l, fill=(225, 225, 230), font=font)
sheet.save(out)
print("sheet", out, sheet.size)
