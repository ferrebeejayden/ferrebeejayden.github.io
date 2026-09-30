"""v6 -> v7 bust / clothing-fit comparison: colour pairs, gray pairs, side silhouettes.

    python3 make_compare_v7.py <v6_dir> <v7_dir> <out.png>
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

old, new, out = sys.argv[1], sys.argv[2], sys.argv[3]
T = 520
SHOTS = [("02_front", "FRONT"), ("01_front34", "FRONT 3/4"), ("03_side", "SIDE"), ("80_elev34", "ELEVATED 3/4"),
         ("81_chest_close", "CHEST / WRAP / ROBE")]
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except OSError:
    F = B = ImageFont.load_default()
cells = []
for sub, tag in (("", ""), ("gray/", "GRAY ")):
    for f, l in SHOTS:
        cells += [(os.path.join(old, sub + f + ".png"), "v6 " + tag + l, (120, 60, 60)),
                  (os.path.join(new, sub + f + ".png"), "v7 " + tag + l, (50, 110, 70))]
cells += [(os.path.join(old, "07b_silhouette_side.png"), "v6 SIDE SILHOUETTE", (120, 60, 60)),
          (os.path.join(new, "07b_silhouette_side.png"), "v7 SIDE SILHOUETTE", (50, 110, 70))]
cells = [c for c in cells if os.path.exists(c[0])]
cols, pad, lab = 6, 10, 30
rows = (len(cells) + cols - 1) // cols
W = cols * T + (cols + 1) * pad
H = 56 + rows * (T + lab + pad) + pad
sheet = Image.new("RGB", (W, H), (22, 23, 27))
d = ImageDraw.Draw(sheet)
d.text((pad + 4, 14), "HEALER / BRAWLER — v7 BUST + CLOTHING-FIT CORRECTION   (v6 vs v7, colour and gray)",
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
