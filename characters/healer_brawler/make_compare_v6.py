"""v5 -> v6 hair-rebuild review sheet.

    python3 make_compare_v6.py <v5_dir> <v6_dir> <out.png>
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

old, new, out = sys.argv[1], sys.argv[2], sys.argv[3]
T = 440
PAIRS = [("02_front", "FRONT"), ("70_h_front", "HAIR FRONT"), ("03_side", "SIDE"), ("72_h_side", "HAIR SIDE"),
         ("76_h_back_sil", "BACK SILHOUETTE"), ("77_h_front_sil", "FRONT SILHOUETTE"), ("78_h_side_sil", "SIDE SILHOUETTE")]
GRAY = [("graybox/70_h_front", "GRAY FRONT"), ("graybox/71_h_34", "GRAY 3/4"), ("graybox/72_h_side", "GRAY SIDE"),
        ("graybox/73_h_rear34", "GRAY REAR 3/4"), ("graybox/74_h_back", "GRAY BACK"), ("graybox/75_h_above", "GRAY ABOVE")]
FINAL = [("02_front", "FINAL FRONT"), ("01_front34", "FINAL FRONT 3/4"), ("03_side", "FINAL SIDE"),
         ("04b_rear34", "FINAL REAR 3/4"), ("04_back", "FINAL BACK"), ("79_hair_close", "HAIR CLOSE-UP"),
         ("71_h_34", "HAIR 3/4"), ("73_h_rear34", "HAIR REAR 3/4"), ("74_h_back", "HAIR BACK"), ("75_h_above", "HAIR ABOVE")]
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except OSError:
    F = B = ImageFont.load_default()
cells = []
for f, l in PAIRS:
    cells += [(os.path.join(old, f + ".png"), "v5 " + l, (120, 60, 60)), (os.path.join(new, f + ".png"), "v6 " + l, (50, 110, 70))]
cells += [(os.path.join(new, f + ".png"), l, (70, 70, 80)) for f, l in GRAY]
cells += [(os.path.join(new, f + ".png"), l, (40, 42, 48)) for f, l in FINAL]
cells = [c for c in cells if os.path.exists(c[0])]
cols, pad, lab = 7, 10, 30
rows = (len(cells) + cols - 1) // cols
W = cols * T + (cols + 1) * pad
H = 56 + rows * (T + lab + pad) + pad
sheet = Image.new("RGB", (W, H), (22, 23, 27))
d = ImageDraw.Draw(sheet)
d.text((pad + 4, 14), "HEALER / BRAWLER — v6 HAIR REBUILD   (v5 vs v6, gray review, final)", fill=(235, 235, 240), font=B)
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
