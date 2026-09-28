"""v1 -> v2 art-pass review sheet: OLD vs NEW pairs, then the new-only views.

    python3 make_compare.py <old_render_dir> <new_render_dir> <out.png>
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

old, new, out = sys.argv[1], sys.argv[2], sys.argv[3]
T = 440
PAIRS = [("01_front34", "FRONT 3/4"), ("02_front", "FRONT"), ("03_side", "SIDE")]
SINGLES = [("04_back", "NEW BACK"), ("07_silhouette_front", "NEW SILHOUETTE FRONT"),
           ("07b_silhouette_side", "NEW SILHOUETTE SIDE"), ("07c_silhouette_34", "NEW SILHOUETTE 3/4"),
           ("07d_silhouette_back", "NEW SILHOUETTE BACK"), ("05_torso_close", "NEW TORSO / BUST / LAPELS"),
           ("05b_torso_side", "NEW TORSO SIDE"), ("05c_shoulder_close", "NEW SHOULDER / SLEEVE"),
           ("06_hair_close", "NEW HAIR"), ("06b_face_close", "NEW FACE"), ("08_arms45", "ARMS 45°"),
           ("09_arms90", "ARMS 90°"), ("10_armraise", "ONE ARM RAISED"), ("11_torso_twist", "TORSO TWIST 22°")]
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except OSError:
    F = B = ImageFont.load_default()
cols, pad, lab = 6, 10, 32
cells = []
for f, l in PAIRS:
    cells += [(os.path.join(old, f + ".png"), "OLD " + l, (120, 60, 60)), (os.path.join(new, f + ".png"), "NEW " + l, (50, 110, 70))]
cells += [(os.path.join(new, f + ".png"), l, (40, 42, 48)) for f, l in SINGLES]
cells = [c for c in cells if os.path.exists(c[0])]
rows = (len(cells) + cols - 1) // cols
W = cols * T + (cols + 1) * pad
H = 56 + rows * (T + lab + pad) + pad
sheet = Image.new("RGB", (W, H), (22, 23, 27))
d = ImageDraw.Draw(sheet)
d.text((pad + 4, 14), "HEALER / BRAWLER — v2 ART-DIRECTION & SILHOUETTE PASS  (OLD = v1, NEW = v2)",
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
