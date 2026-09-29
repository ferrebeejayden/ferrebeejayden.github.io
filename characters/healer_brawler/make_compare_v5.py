"""v3 -> v5 (Roblox-first) review sheet.

    python3 make_compare_v5.py <v3_render_dir> <v5_render_dir> <out.png>
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

old, new, out = sys.argv[1], sys.argv[2], sys.argv[3]
T = 420
PAIRS = [("01_front34", "FRONT 3/4"), ("02_front", "FRONT"), ("03_side", "SIDE"), ("04_back", "BACK")]
GRAY = [("graybox/02_front", "GRAY FRONT"), ("graybox/01_front34", "GRAY 3/4"), ("graybox/03_side", "GRAY SIDE"),
        ("graybox/04_back", "GRAY BACK"), ("graybox/08_arms45", "GRAY ARMS 45°"), ("graybox/09_arms90", "GRAY ARMS 90°"),
        ("graybox/30_hair_front", "GRAY HAIR FRONT"), ("graybox/31_hair_side", "GRAY HAIR SIDE"), ("graybox/32_hair_back", "GRAY HAIR BACK")]
SINGLES = [("07_silhouette_front", "SILHOUETTE FRONT"), ("07b_silhouette_side", "SILHOUETTE SIDE"),
           ("07c_silhouette_34", "SILHOUETTE 3/4"), ("30_hair_front", "HAIR FRONT"), ("31_hair_side", "HAIR SIDE"),
           ("32_hair_back", "HAIR BACK"), ("60_chest_wrap", "CHEST / WRAPPED TOP"), ("61_shoulder_arm", "SHOULDER / ARM"),
           ("08_arms45", "ARMS 45°"), ("09_arms90", "ARMS 90°"), ("08b_arms20", "ARMS 20°"),
           ("10_armraise", "ONE ARM RAISED"), ("11_torso_twist", "TORSO TWIST 22°"), ("63_robe", "ROBE MATERIAL"),
           ("64_sash_inner", "SASH / INNER GARMENT"), ("62_face", "FACE")]
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except OSError:
    F = B = ImageFont.load_default()
cells = []
for f, l in PAIRS:
    cells += [(os.path.join(old, f + ".png"), "v3 " + l, (120, 60, 60)), (os.path.join(new, f + ".png"), "v5 " + l, (50, 110, 70))]
cells += [(os.path.join(new, f + ".png"), l, (70, 70, 80)) for f, l in GRAY]
cells += [(os.path.join(new, f + ".png"), l, (40, 42, 48)) for f, l in SINGLES]
cells = [c for c in cells if os.path.exists(c[0])]
cols, pad, lab = 8, 10, 30
rows = (len(cells) + cols - 1) // cols
W = cols * T + (cols + 1) * pad
H = 56 + rows * (T + lab + pad) + pad
sheet = Image.new("RGB", (W, H), (22, 23, 27))
d = ImageDraw.Draw(sheet)
d.text((pad + 4, 14), "HEALER / BRAWLER — v5 ROBLOX-FIRST STYLE CORRECTION   (v3 vs v5, gray review, final)",
       fill=(235, 235, 240), font=B)
for i, (p, l, tint) in enumerate(cells):
    r, c = divmod(i, cols)
    x0, y0 = pad + c * (T + pad), 56 + r * (T + lab + pad)
    im = Image.open(p).convert("RGB"); im.thumbnail((T, T), Image.LANCZOS)
    d.rectangle([x0, y0, x0 + T, y0 + T], fill=(40, 42, 48))
    sheet.paste(im, (x0 + (T - im.width) // 2, y0 + (T - im.height) // 2))
    d.rectangle([x0, y0 + T, x0 + T, y0 + T + lab - 4], fill=tint)
    tw = d.textlength(l, font=F)
    d.text((x0 + (T - tw) / 2, y0 + T + 5), l, fill=(240, 240, 244), font=F)
sheet.save(out)
print("compare sheet", out, sheet.size)
