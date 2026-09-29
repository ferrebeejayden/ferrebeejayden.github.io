"""v2 -> v3 review sheet: v2 vs v3 pairs, v2 vs v3 hair silhouettes, then v3-only views.

    python3 make_compare_v3.py <v2_render_dir> <v3_render_dir> <out.png>
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

old, new, out = sys.argv[1], sys.argv[2], sys.argv[3]
T = 420
PAIRS = [("01_front34", "FRONT 3/4"), ("02_front", "FRONT"), ("03_side", "SIDE"), ("04_back", "BACK"),
         ("50_hairsil_front", "HAIR SIL. FRONT"), ("51_hairsil_side", "HAIR SIL. SIDE"), ("52_hairsil_back", "HAIR SIL. BACK")]
SINGLES = [("20_shoulder_neutral", "SHOULDER NEUTRAL"), ("20b_shoulder_neutral_back", "SHOULDER NEUTRAL (BACK)"),
           ("21_shoulder_20", "SHOULDER 20°"), ("22_shoulder_45", "SHOULDER 45°"), ("23_shoulder_90", "SHOULDER 90°"),
           ("23b_shoulder_raise", "SHOULDER ARM RAISED"), ("30_hair_front", "HAIR FRONT"), ("31_hair_side", "HAIR SIDE"),
           ("32_hair_back", "HAIR BACK"), ("40_robe_material", "ROBE MATERIAL"), ("41_sash_lapel_material", "SASH / LAPEL MATERIAL"),
           ("42_boots_wraps", "BOOTS / WRAPS"), ("08b_arms20", "ARMS 20°"), ("08_arms45", "ARMS 45°"),
           ("09_arms90", "ARMS 90°"), ("10_armraise", "ONE ARM RAISED"), ("11_torso_twist", "TORSO TWIST 22°"),
           ("07_silhouette_front", "SILHOUETTE FRONT")]
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except OSError:
    F = B = ImageFont.load_default()
cells = []
for f, l in PAIRS:
    cells += [(os.path.join(old, f + ".png"), "v2 " + l, (120, 60, 60)), (os.path.join(new, f + ".png"), "v3 " + l, (50, 110, 70))]
cells += [(os.path.join(new, f + ".png"), l, (40, 42, 48)) for f, l in SINGLES]
cells = [c for c in cells if os.path.exists(c[0])]
cols, pad, lab = 8, 10, 30
rows = (len(cells) + cols - 1) // cols
W = cols * T + (cols + 1) * pad
H = 56 + rows * (T + lab + pad) + pad
sheet = Image.new("RGB", (W, H), (22, 23, 27))
d = ImageDraw.Draw(sheet)
d.text((pad + 4, 14), "HEALER / BRAWLER — v3: SHOULDER CONNECTION · FEMININE HAIR · MATERIAL DEPTH   (v2 vs v3)",
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
