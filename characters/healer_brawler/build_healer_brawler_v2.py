"""
Healer / Brawler unit v2 -- art-direction / silhouette pass on the supplied Roblox R15 rig.
(v1 = build_healer_brawler.py, kept unchanged.)  Same rig, weighting pipeline and garment structure;
slimmer shoulders & sleeves, hourglass torso, softer bust, thinner lapels, tapered coat,
new hair and face.

Original adult anime-style character ("Sera, the Jade Fist" -- working name).
Reusable template: every body part / garment is generated from shared parametric
functions (torso surface, garment offsets, ribbons, hair locks, face decals), then
skinned to the untouched R15 armature `__Rig`.

Run (Blender 4.2 or the `bpy` module):
    python3 build_healer_brawler.py <blank_rig.blend> <output.blend>

The blank rig file is only read; the result is written to a NEW .blend.
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
RIG_PATH, OUT_PATH = os.path.abspath(argv[0]), os.path.abspath(argv[1])
assert RIG_PATH != OUT_PATH, "never overwrite the blank rig"

bpy.ops.wm.open_mainfile(filepath=RIG_PATH)
ARM = bpy.data.objects["__Rig"]

# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------
def sstep(a, b, x):
    """smoothstep that also works with a > b (falling edge)."""
    if a == b:
        return 1.0 if x >= a else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)

class Curve1D:
    """monotone cubic (PCHIP) interpolation through (x, y) keys."""
    def __init__(self, keys):
        self.x = [k[0] for k in keys]; self.y = [k[1] for k in keys]
        n = len(keys); d = [(self.y[i + 1] - self.y[i]) / (self.x[i + 1] - self.x[i]) for i in range(n - 1)]
        m = [0.0] * n
        m[0], m[-1] = d[0], d[-1]
        for i in range(1, n - 1):
            m[i] = 0.0 if d[i - 1] * d[i] <= 0 else 2 / (1 / d[i - 1] + 1 / d[i])
        self.m = m
    def __call__(self, x):
        xs, ys, m = self.x, self.y, self.m
        if x <= xs[0]: return ys[0]
        if x >= xs[-1]: return ys[-1]
        for i in range(len(xs) - 1):
            if x <= xs[i + 1]:
                h = xs[i + 1] - xs[i]; t = (x - xs[i]) / h
                h00 = 2 * t**3 - 3 * t**2 + 1; h10 = t**3 - 2 * t**2 + t
                h01 = -2 * t**3 + 3 * t**2; h11 = t**3 - t**2
                return h00 * ys[i] + h10 * h * m[i] + h01 * ys[i + 1] + h11 * h * m[i + 1]

def srgb(r, g, b):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (c(r), c(g), c(b), 1.0)

def catmull(points, samples_per_seg=10):
    pts = [Vector(p) for p in points]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(samples_per_seg):
            t = k / samples_per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out

def resample(pts, n):
    L = [0.0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + (b - a).length)
    out, j = [], 0
    for i in range(n):
        s = L[-1] * i / (n - 1)
        while j < len(L) - 2 and L[j + 1] < s:
            j += 1
        seg = max(L[j + 1] - L[j], 1e-9)
        out.append(pts[j].lerp(pts[j + 1], (s - L[j]) / seg))
    return out

def grid_bm(rows, wrap=False, bm=None, cap_start=False, cap_end=False):
    """quad grid from a list of rows (each a list of Vectors of equal length)."""
    bm = bm or bmesh.new()
    V = [[bm.verts.new(p) for p in r] for r in rows]
    n = len(rows[0])
    for i in range(len(rows) - 1):
        for j in range(n if wrap else n - 1):
            j2 = (j + 1) % n
            try:
                bm.faces.new((V[i][j], V[i][j2], V[i + 1][j2], V[i + 1][j]))
            except ValueError:
                pass
    for flag, row, rev in ((cap_start, V[0], True), (cap_end, V[-1], False)):
        if flag:
            c = bm.verts.new(sum((v.co for v in row), Vector()) / len(row))
            for j in range(n if wrap else n - 1):
                a, b = row[j], row[(j + 1) % n]
                try:
                    bm.faces.new((c, b, a) if rev else (c, a, b))
                except ValueError:
                    pass
    return bm

COLL = bpy.data.collections.new("HealerBrawler_Unit")
bpy.context.scene.collection.children.link(COLL)
MATS = {}

def mat(name, rgba, rough=0.6, metal=0.0, sheen=0.0, emit=0.0, spec=0.35, coat=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new("HB_" + name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Sheen Tint"].default_value = (1, 1, 1, 1)
    b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = rgba
        b.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = rgba
    MATS[name] = m
    return m

def fix_normals(bm, center_fn=None):
    bm.normal_update()
    if center_fn is None:
        return
    score = 0.0
    for f in bm.faces:
        c = f.calc_center_median()
        score += f.normal.dot(c - center_fn(c))
    if score < 0:
        for f in bm.faces:
            f.normal_flip()
        bm.normal_update()

def bm_to_obj(bm, name, material, smooth=True, parent_coll=COLL):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    if isinstance(material, (list, tuple)):
        for m in material:
            me.materials.append(m)
    else:
        me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    parent_coll.objects.link(ob)
    return ob

def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)

def solidify(ob, thick, offset=-1.0, rim=True, even=False):
    m = ob.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thick; m.offset = offset; m.use_even_offset = even
    m.use_rim = rim; m.use_quality_normals = True
    apply_mods(ob)

def sharpen(ob, deg=48):
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(deg))
    except Exception:
        pass

def join(objs, name):
    base = objs[0]
    bm = bmesh.new()
    mats = []
    for o in objs:
        tmp = bmesh.new(); tmp.from_mesh(o.data)
        remap = []
        for m in o.data.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        for f in tmp.faces:
            f.material_index = remap[f.material_index] if remap else 0
        me = bpy.data.meshes.new("tmp"); tmp.to_mesh(me); tmp.free()
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    weighted = all(len(o.vertex_groups) for o in objs)
    for o in objs:
        me = o.data; bpy.data.objects.remove(o); bpy.data.meshes.remove(me)
    ob = bm_to_obj(bm, name, mats)
    if weighted:            # pieces were skinned with identical group order -> keep their weights
        for b in DEFORM:
            ob.vertex_groups.new(name=b)
    return ob

# ---------------------------------------------------------------------------
# skinning
# ---------------------------------------------------------------------------
DEFORM = ["LowerTorso", "UpperTorso", "Head",
          "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand",
          "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"]

def skin(ob, wfn, bind=True):
    for b in DEFORM:
        ob.vertex_groups.new(name=b)
    groups = {g.name: g for g in ob.vertex_groups}
    for v in ob.data.vertices:
        w = wfn(v.co)
        w = {k: x for k, x in w.items() if x > 1e-4}
        tot = sum(w.values())
        for k, x in w.items():
            groups[k].add([v.index], x / tot, "REPLACE")
    if bind:
        bind_to_rig(ob)

def bind_to_rig(ob):
    ob.parent = ARM
    ob.matrix_parent_inverse = Matrix.Identity(4)
    m = ob.modifiers.new("Armature", "ARMATURE")
    m.object = ARM; m.use_vertex_groups = True; m.use_deform_preserve_volume = False

def side(x):
    return "Left" if x > 0 else "Right"

def w_torso(p, arm_blend=0.4, neck=True):
    """torso-attached geometry: Lower/UpperTorso split at the waist, shoulders feed into the arm."""
    up = sstep(2.45, 2.95, p.z)
    w = {"UpperTorso": up, "LowerTorso": 1 - up}
    a = sstep(0.70, 0.90, abs(p.x)) * sstep(3.8, 4.02, p.z) * arm_blend
    if a > 0:
        w = {k: v * (1 - a) for k, v in w.items()}
        w[side(p.x) + "UpperArm"] = a
    if neck and p.z > 4.12:
        h = sstep(4.14, 4.32, p.z)
        w = {k: v * (1 - h) for k, v in w.items()}
        w["Head"] = h
    return w

def w_skirt(p, leg_amt=0.55):
    """coat lower panels / sash tails: waist -> hips -> follow legs toward the hem."""
    if p.z > 2.45:
        return w_torso(p)
    base = w_torso(p)
    leg = sstep(2.25, 1.25, p.z) * leg_amt
    lr = sstep(-0.3, 0.3, p.x)
    w = {k: v * (1 - leg) for k, v in base.items()}
    w["LeftUpperLeg"] = leg * lr
    w["RightUpperLeg"] = leg * (1 - lr)
    return w

def w_arm(p, torso_blend=0.12):
    s = side(p.x)
    lo = sstep(3.3, 2.95, p.z)
    w = {s + "UpperArm": 1 - lo, s + "LowerArm": lo}
    t = sstep(0.98, 0.82, abs(p.x)) * sstep(3.85, 4.1, p.z) * torso_blend
    if t > 0:
        w = {k: v * (1 - t) for k, v in w.items()}
        w["UpperTorso"] = t
    return w

def w_leg(p):
    s = side(p.x)
    if p.z < 0.2:
        return {s + "Foot": 1.0}
    lo = sstep(1.35, 1.05, p.z)
    w = {s + "UpperLeg": 1 - lo, s + "LowerLeg": lo}
    t = sstep(1.95, 2.3, p.z)
    if t > 0:
        w = {k: v * (1 - t) for k, v in w.items()}
        w["LowerTorso"] = t
    return w

def w_rigid(bone):
    return lambda p: {bone: 1.0}

def w_side_rigid(suffix):
    return lambda p: {side(p.x) + suffix: 1.0}

# ---------------------------------------------------------------------------
# palette
# ---------------------------------------------------------------------------
SKIN = mat("Skin", srgb(248, 214, 192), rough=0.55, spec=0.3)
CREAM = mat("InnerTop_Cream", srgb(240, 228, 204), rough=0.8, sheen=0.25)
CREAM_TRIM = mat("InnerTop_Collar", srgb(190, 164, 128), rough=0.75, sheen=0.25)
GREEN = mat("Coat_Green", srgb(42, 68, 52), rough=0.78, sheen=0.35)
GREEN_TRIM = mat("Coat_Trim", srgb(17, 30, 23), rough=0.7, sheen=0.3)
SASH = mat("Sash_Navy", srgb(20, 26, 46), rough=0.7, sheen=0.3)
SASH2 = mat("Sash_Slate", srgb(52, 62, 94), rough=0.7, sheen=0.3)
CORD = mat("Cord_Gold", srgb(212, 166, 70), rough=0.4, metal=0.4)
PANTS = mat("Pants_Charcoal", srgb(38, 38, 44), rough=0.8, sheen=0.3)
WRAP = mat("Wraps", srgb(226, 214, 192), rough=0.85, sheen=0.2)
BOOT = mat("Boots", srgb(44, 30, 26), rough=0.5, spec=0.4)
SOLE = mat("Boot_Sole", srgb(22, 16, 14), rough=0.7)
LEATHER = mat("Pouch_Leather", srgb(104, 62, 36), rough=0.55)
HAIR = mat("Hair_Auburn", srgb(118, 32, 22), rough=0.45, spec=0.4, sheen=0.15)
GOLD = mat("Ornament_Gold", srgb(224, 176, 82), rough=0.28, metal=1.0)
JADE = mat("Ornament_Jade", srgb(58, 168, 124), rough=0.15, coat=1.0)

def hair_gradient(m, low, high, z0, z1):
    """rich auburn: darker toward the nape/tips, warmer at the crown (render look only)."""
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = z0; mr.inputs["From Max"].default_value = z1
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = low; cr.color_ramp.elements[1].color = high
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], cr.inputs["Fac"])
    nt.links.new(cr.outputs["Color"], bsdf.inputs["Base Color"])
hair_gradient(HAIR, srgb(66, 16, 12), srgb(146, 44, 28), 3.4, 5.35)

ARM_CX = 1.30     # visual centre of the (slimmed) arms; bones are untouched
LEG_CX = 0.45     # visual centre of the (slimmed) legs

# ---------------------------------------------------------------------------
# 1. parametric torso surface (the shared body the garments are offset from)
# ---------------------------------------------------------------------------
TW = Curve1D([(1.75, .90), (2.15, .90), (2.45, .78), (2.75, .60), (3.02, .65), (3.35, .73), (3.68, .76),
              (3.9, .74), (4.0, .64), (4.06, .46), (4.12, .25), (4.20, .205), (4.50, .195)])
TD = Curve1D([(1.75, .47), (2.15, .48), (2.45, .43), (2.75, .355), (3.02, .375), (3.35, .40), (3.68, .41),
              (3.9, .39), (4.0, .34), (4.06, .28), (4.12, .22), (4.20, .19), (4.50, .18)])
TN = Curve1D([(1.75, 2.8), (2.40, 2.6), (2.75, 2.2), (3.40, 2.4), (3.90, 2.8), (4.08, 2.3), (4.20, 2.0), (4.5, 2.0)])
TY = Curve1D([(1.75, .04), (2.3, .04), (2.75, .01), (3.4, -.01), (4.0, .02), (4.5, .06)])  # posture: back curve

# coat: follows the shoulders/bust, tapers into the waist, flares toward a long hem
CW = Curve1D([(0.70, 1.02), (1.20, .97), (1.70, .92), (2.10, .88), (2.45, .80), (2.78, .65), (3.02, .66),
              (3.35, .73), (3.68, .76), (3.9, .74), (4.0, .64), (4.06, .46), (4.12, .25), (4.20, .205), (4.50, .195)])
CD = Curve1D([(0.70, .62), (1.20, .58), (1.70, .55), (2.10, .52), (2.45, .47), (2.78, .41), (3.02, .39),
              (3.35, .40), (3.68, .41), (3.9, .39), (4.0, .34), (4.06, .28), (4.12, .22), (4.20, .19), (4.50, .18)])

BUST = dict(xc=.30, zc=3.30, rx=.40, rzu=.62, rzd=.33, A=.40, p=2.0)   # p=2: soft falloff into the chest wall
INNER = {"skin": 0.55, "cloth": 0.22, "coat": 0.2}      # central separation (1 = deep, 0 = none)
DRAPE = {"skin": 1.0, "cloth": 1.35, "coat": 1.9}        # how far the fabric falls from the underside

def bust_disp(x, z, mode):
    B = BUST
    dx = abs(x) - B["xc"]
    if dx < 0:
        dx *= INNER[mode]
    dz = z - B["zc"]
    rz = B["rzu"] if dz > 0 else B["rzd"] * DRAPE[mode]
    r2 = (dx / B["rx"]) ** 2 + (dz / rz) ** 2
    if r2 >= 1:
        return 0.0
    return B["A"] * (1 - r2) ** B["p"]

def torso_P(t, z, mode="skin"):
    """t in degrees: 0 = +X (character left), 90 = front (-Y), 180 = right, 270 = back."""
    if mode == "coat":
        W, D = CW(z), CD(z)
    else:
        W, D = TW(z), TD(z)
    n = TN(z)
    c, s = math.cos(math.radians(t)), math.sin(math.radians(t))
    x = W * math.copysign(abs(c) ** (2 / n), c)
    y = -D * math.copysign(abs(s) ** (2 / n), s) + TY(z)
    if s > 0:
        b = bust_disp(x, z, mode) * sstep(0.0, 0.35, s)
        y -= b
        x += b * 0.12 * math.tanh(x / 0.12)      # continuous across the centre line
    return Vector((x, y, z))

def underarm(p, off):
    """flatten every layer's side where the blocky arm hangs, so sleeve and body meet cleanly."""
    lim = 0.86 + off * 0.5
    if abs(p.x) <= lim:
        return p
    k = sstep(2.5, 2.62, p.z) * sstep(4.06, 3.95, p.z) * sstep(0.62, 0.5, abs(p.y - TY(p.z)))
    if k <= 0:
        return p
    q = p.copy()
    ax = abs(p.x)
    soft = lim + 0.03 * math.tanh((ax - lim) / 0.03)       # smooth clamp
    q.x = math.copysign(ax + (soft - ax) * k, p.x)
    return q

def surf(t, z, mode, off):
    """garment surface = body surface pushed out along its normal."""
    return underarm(_surf(t, z, mode, off), off)

def _surf(t, z, mode, off):
    p = torso_P(t, z, mode)
    if off == 0:
        return p
    dt, dz = 0.4, 0.004
    a = torso_P(t + dt, z, mode) - torso_P(t - dt, z, mode)
    b = torso_P(t, z + dz, mode) - torso_P(t, z - dz, mode)
    n = b.cross(a).normalized()
    radial = Vector((p.x, p.y - TY(z), 0))
    if n.dot(radial) < 0:
        n = -n
    return p + n * off

def t_for_x(z, xe, mode, off):
    """front-quadrant angle where the garment surface reaches |x| = xe (bisection)."""
    lo, hi = 0.0, 90.0   # x decreases from lo to hi
    for _ in range(30):
        mid = (lo + hi) / 2
        if surf(mid, z, mode, off).x > xe:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def zlist(z0, z1, step, top_fine=True):
    zs, z = [], z0
    while z < min(z1, 3.9) - 1e-6:
        zs.append(z); z += step
    if top_fine:
        extra = [3.9, 3.93, 3.96, 3.985, 4.005, 4.025, 4.045, 4.065, 4.085, 4.105, 4.13, 4.16, 4.2, 4.26, 4.33, 4.4, 4.47]
        zs += [e for e in extra if e <= z1 + 1e-6 and e >= z0]
    else:
        zs.append(z1)
    return zs

def ring(z, mode, off, n, t0=0.0, t1=360.0, closed=True):
    if closed:
        return [surf(t0 + (t1 - t0) * j / n, z, mode, off) for j in range(n)]
    return [surf(t0 + (t1 - t0) * j / (n - 1), z, mode, off) for j in range(n)]

axis_center = lambda c: Vector((0, TY(c.z), c.z))

# body torso (skin) -- neck, shoulders, bust, waist, hips
rows = [ring(z, "skin", 0.0, 48) for z in zlist(2.02, 4.47, 0.08)]
bm = grid_bm(rows, wrap=True, cap_start=True)
fix_normals(bm, axis_center)
body_torso = bm_to_obj(bm, "Body_Torso", SKIN)
skin(body_torso, lambda p: w_torso(p, arm_blend=0.4))

# ---------------------------------------------------------------------------
# 2. R15 blocky foundation (limbs) -- copies of the supplied parts, skinned rigidly
# ---------------------------------------------------------------------------
BLANK = bpy.data.collections.get("Collection")
if BLANK:
    BLANK.name = "R15_BlankParts_Reference"
    BLANK.hide_render = True
    for o in BLANK.objects:
        o.hide_set(True)
limb_parts = ["LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand",
              "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"]
bm = bmesh.new()
owner = []
for pn in limb_parts:
    src = bpy.data.objects[pn]
    me = src.data.copy()
    me.transform(src.matrix_world)
    k = {"UpperArm": 0.44, "LowerArm": 0.5, "Hand": 0.54, "UpperLeg": 0.6, "LowerLeg": 0.6, "Foot": 0.66}
    k = next(v for kk, v in k.items() if pn.endswith(kk))
    lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in me.vertices) for i in range(3)])
    c = (lo + hi) / 2                                  # bbox centre (vertex mean is skewed on these parts)
    tx = math.copysign(ARM_CX if "Arm" in pn or "Hand" in pn else LEG_CX, c.x)
    for v in me.vertices:
        v.co.x = tx + (v.co.x - c.x) * k
        v.co.y = c.y + (v.co.y - c.y) * k
        if pn.endswith("LowerArm"):
            v.co.z = min(v.co.z, 2.6)
        if pn.endswith("UpperArm"):
            v.co.z = min(v.co.z, 3.8)          # stays inside the rounded shoulder cap
    bm.from_mesh(me)
    owner += [pn] * (len(bm.verts) - len(owner))
    bpy.data.meshes.remove(me)
body_limbs = bm_to_obj(bm, "Body_Limbs", SKIN)
for pn in DEFORM:
    body_limbs.vertex_groups.new(name=pn)
for v, pn in zip(body_limbs.data.vertices, owner):
    body_limbs.vertex_groups[pn].add([v.index], 1.0, "REPLACE")
body_limbs.parent = ARM
body_limbs.modifiers.new("Armature", "ARMATURE").object = ARM

# ---------------------------------------------------------------------------
# 3. head
# ---------------------------------------------------------------------------
HC = Vector((0.0, -0.02, 4.65))
FZ = HC.z - 4.60
HR = Vector((0.555, 0.525, 0.545))
HN = 2.7

def head_dir(theta, phi):
    """theta: 0 = front (-Y), +90 = character left (+X). phi: 0 = top."""
    th, ph = math.radians(theta), math.radians(phi)
    return Vector((math.sin(ph) * math.sin(th), -math.sin(ph) * math.cos(th), math.cos(ph)))

def head_P(theta, phi, off=0.0):
    d = head_dir(theta, phi)
    r = 1.0 / ((abs(d.x) / HR.x) ** HN + (abs(d.y) / HR.y) ** HN + (abs(d.z) / HR.z) ** HN) ** (1 / HN)
    p = d * r
    if p.z < 0:                           # anime jaw: narrower + slightly pointed chin
        k = (-p.z / HR.z)
        p.x *= 1 - 0.27 * k ** 1.5
        if p.y < 0:
            p.y *= 1 - 0.12 * k ** 2
        p.y -= 0.045 * k ** 3 * max(0.0, 1 - abs(p.x) / 0.26) * (1 if p.y < 0 else 0)
    p = HC + p
    if off:
        e = 0.3
        a = head_P(theta + e, phi) - head_P(theta - e, phi)
        b = head_P(theta, phi + e) - head_P(theta, phi - e)
        n = a.cross(b).normalized()
        if n.dot(p - HC) < 0:
            n = -n
        p = p + n * off
    return p

rows = [[head_P(360 * j / 56, 180 * i / 34) for j in range(56)] for i in range(35)]
bm = grid_bm(rows, wrap=True)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
fix_normals(bm, lambda c: HC)
head = bm_to_obj(bm, "Head_Mesh", SKIN)
head_bm = bmesh.new(); head_bm.from_mesh(head.data)
HEAD_BVH = BVHTree.FromBMesh(head_bm)

# ---------------------------------------------------------------------------
# 4. face (projected decal geometry -- original design)
# ---------------------------------------------------------------------------
FACE_M = {
    "sclera": mat("Eye_White", srgb(252, 250, 246), rough=0.4),
    "iris": mat("Eye_IrisRim", srgb(88, 40, 14), rough=0.3),
    "gold": mat("Eye_IrisGold", srgb(232, 162, 46), rough=0.3, emit=0.15),
    "pupil": mat("Eye_Pupil", srgb(38, 16, 8), rough=0.3),
    "hi": mat("Eye_Highlight", srgb(255, 255, 255), rough=0.2, emit=1.5),
    "lash": mat("Face_Lash", srgb(34, 16, 14), rough=0.6),
    "lid": mat("Face_LowerLid", srgb(150, 84, 70), rough=0.6),
    "brow": mat("Face_Brow", srgb(84, 24, 18), rough=0.6),
    "mouth": mat("Face_Mouth", srgb(166, 72, 62), rough=0.5),
    "nose": mat("Face_Nose", srgb(222, 160, 138), rough=0.6),
    "blush": mat("Face_Blush", srgb(238, 160, 148), rough=0.6),
}
FACE_KEYS = list(FACE_M)
face_bm = bmesh.new()

def project(x, z, eps):
    hit = HEAD_BVH.ray_cast(Vector((x, -3.0, z + FZ)), Vector((0, 1, 0)))
    loc, nor = hit[0], hit[1]
    return loc + nor * eps

def add_poly(pts2d, center2d, eps, key, rings=4):
    V = [[face_bm.verts.new(project(center2d[0], center2d[1], eps))]]
    for k in range(1, rings + 1):
        f = k / rings
        V.append([face_bm.verts.new(project(center2d[0] + (p[0] - center2d[0]) * f,
                                            center2d[1] + (p[1] - center2d[1]) * f, eps)) for p in pts2d])
    n = len(pts2d); mi = FACE_KEYS.index(key)
    for j in range(n):
        f = face_bm.faces.new((V[0][0], V[1][j], V[1][(j + 1) % n])); f.material_index = mi
    for k in range(1, rings):
        for j in range(n):
            f = face_bm.faces.new((V[k][j], V[k + 1][j], V[k + 1][(j + 1) % n], V[k][(j + 1) % n]))
            f.material_index = mi

def add_stroke(pts2d, widths, eps, key, align=0.0):
    """ribbon along a 2D polyline; align 0 = centred, 1 = grows to the left of travel."""
    pts = [Vector((p[0], p[1])) for p in pts2d]
    L, R = [], []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        nrm = Vector((-d.y, d.x))
        w = widths[i]
        a = p + nrm * w * (0.5 + 0.5 * align)
        b = p - nrm * w * (0.5 - 0.5 * align)
        L.append(face_bm.verts.new(project(a.x, a.y, eps)))
        R.append(face_bm.verts.new(project(b.x, b.y, eps)))
    mi = FACE_KEYS.index(key)
    for i in range(len(pts) - 1):
        f = face_bm.faces.new((R[i], R[i + 1], L[i + 1], L[i])); f.material_index = mi

def bez(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        out.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * d
                         for a, b, c, d in zip(p0, p1, p2, p3)))
    return out

def interp_v(curve, u):
    for a, b in zip(curve, curve[1:]):
        if a[0] <= u <= b[0]:
            f = (u - a[0]) / (b[0] - a[0] + 1e-9)
            return a[1] + (b[1] - a[1]) * f
    return curve[0][1] if u < curve[0][0] else curve[-1][1]

EYE_Z = 4.55
for ex in (-0.19, 0.19):
    o = 1 if ex > 0 else -1
    W = lambda u, v: (ex + o * u, EYE_Z + v)
    # mature almond: flatter upper lid, outer corner lifted
    upper = bez((-0.072, -0.006), (-0.045, 0.058), (0.038, 0.074), (0.096, 0.042), 18)
    lower = bez((-0.072, -0.006), (-0.03, -0.054), (0.058, -0.05), (0.096, 0.042), 18)
    sclera = [W(*p) for p in upper] + [W(*p) for p in reversed(lower[1:-1])]
    if o < 0:
        sclera.reverse()
    add_poly(sclera, W(0.01, 0.005), 0.003, "sclera")

    def ellipse(cu, cv, ru, rv, n=28, pad=0.004):
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            u, v = cu + ru * math.cos(a), cv + rv * math.sin(a)
            u = max(-0.068, min(0.092, u))
            v = min(v, interp_v(upper, u) - pad)
            v = max(v, interp_v(lower, u) + pad * 0.5)
            pts.append(W(u, v))
        if o < 0:
            pts.reverse()
        return pts
    add_poly(ellipse(0.008, -0.002, 0.054, 0.072), W(0.008, -0.002), 0.005, "iris")
    add_poly(ellipse(0.008, -0.014, 0.045, 0.054), W(0.008, -0.014), 0.007, "gold")
    add_poly(ellipse(0.008, 0.034, 0.05, 0.026, 20, 0.002), W(0.008, 0.03), 0.008, "iris")     # lid shadow on iris
    add_poly(ellipse(0.008, -0.004, 0.016, 0.032), W(0.008, -0.004), 0.009, "pupil")
    add_poly(ellipse(-0.014, 0.018, 0.017, 0.02, 16, 0.0), W(-0.014, 0.018), 0.011, "hi")
    add_poly(ellipse(0.03, -0.034, 0.008, 0.007, 12, 0.0), W(0.03, -0.034), 0.011, "hi")
    # heavy upper lash line with a long lifted wing
    lash = upper + [(0.114, 0.058), (0.134, 0.074)]
    n = len(lash)
    widths = [0.007 + 0.019 * sstep(0.0, 0.6, i / (n - 3)) for i in range(n - 2)] + [0.013, 0.0]
    add_stroke([W(*p) for p in lash], widths, 0.012, "lash", align=o * 1.0)
    low = [W(*p) for p in lower[9:]] + [W(0.108, 0.036)]
    add_stroke(low, [0.0] + [0.006] * (len(low) - 2) + [0.0], 0.005, "lid")
    # double-lid crease: reads older / more confident
    crease = [W(u, v + 0.024) for u, v in upper[5:16]]
    add_stroke(crease, [0.0] + [0.0035] * (len(crease) - 2) + [0.0], 0.004, "lid")
    # brows: slim, angular, wearer's left raised a touch
    rs = 0.014 if o > 0 else 0.0
    brow = catmull([W(-0.066, 0.146), W(0.012, 0.166 + rs), W(0.07, 0.17 + rs), W(0.128, 0.145 + rs * 0.5)], 6)
    bw = [0.017 - 0.014 * (i / (len(brow) - 1)) ** 1.2 for i in range(len(brow))]
    add_stroke([(p.x, p.y) for p in brow], bw, 0.004, "brow")
    for k in range(2):
        cx = ex + o * (0.03 + 0.032 * k)
        add_stroke([(cx - o * 0.008, 4.425), (cx + o * 0.012, 4.448)], [0.005, 0.005], 0.003, "blush")

add_stroke([(0.016, 4.43), (0.008, 4.413), (-0.004, 4.41)], [0.003, 0.008, 0.003], 0.003, "nose")
mouth = catmull([(-0.056, 4.318), (-0.018, 4.307), (0.03, 4.309), (0.07, 4.33)], 8)
mw = [0.004 + 0.007 * math.sin(math.pi * i / (len(mouth) - 1)) for i in range(len(mouth))]
add_stroke([(p.x, p.y) for p in mouth], mw, 0.004, "mouth")
add_stroke([(0.064, 4.326), (0.076, 4.336), (0.082, 4.331)], [0.004, 0.005, 0.0], 0.004, "mouth")  # smirk corner
add_stroke([(-0.012, 4.288), (0.004, 4.285), (0.02, 4.288)], [0.0, 0.004, 0.0], 0.003, "nose")      # lower lip hint

face = bm_to_obj(face_bm, "Face_Features", [FACE_M[k] for k in FACE_KEYS])
skin(head, w_rigid("Head"))
skin(face, w_rigid("Head"))

# ---------------------------------------------------------------------------
# 5. cream wrapped inner top (crossed lapels over the bust)
# ---------------------------------------------------------------------------
IT_OFF = 0.03
Z_CROSS = 3.36
GAP = Curve1D([(Z_CROSS, 0.0), (3.62, 0.12), (3.9, 0.21), (4.13, 0.25)])

def inner_gap(z):
    return 0.0 if z <= Z_CROSS else GAP(z)

rows = []
N_IT = 56
zs_it = zlist(2.46, 4.13, 0.07)
for z in zs_it:
    g = inner_gap(z)
    d = 90 - t_for_x(z, g, "cloth", IT_OFF) if g > 0 else 0.0
    t0, t1 = 90 - d, -270 + d
    rows.append(ring(z, "cloth", IT_OFF, N_IT, t0, t1, closed=False))
bm = grid_bm(rows)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
fix_normals(bm, axis_center)
IT_BM = bm.copy()
IT_BVH = BVHTree.FromBMesh(IT_BM)
inner_top = bm_to_obj(bm, "InnerTop", CREAM)
solidify(inner_top, 0.012)
sharpen(inner_top)
skin(inner_top, w_torso)

def snap(bvh, p, lift):
    loc, nor, _, _ = bvh.find_nearest(p)
    return loc + nor * lift, nor

def front_hit(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -4.0, z)), Vector((0, 1, 0)))
    if hit[0] is None:
        print("front_hit miss", round(x, 3), round(z, 3))
        for dz in (0.01, -0.01, 0.02, -0.02, 0.04, -0.04):
            hit = bvh.ray_cast(Vector((x, -4.0, z + dz)), Vector((0, 1, 0)))
            if hit[0] is not None:
                return hit[0] - Vector((0, 0, dz)), hit[1]
    return hit[0], hit[1]

def ribbon_bm(path, normals, width_fn, lift, bm=None, across=3, dome=0.006, shift_fn=None):
    bm = bm or bmesh.new()
    rows = []
    n = len(path)
    for i in range(n):
        p, nr = path[i], normals[i]
        T = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        B = T.cross(nr).normalized()
        s = i / (n - 1)
        w = width_fn(s)
        sh = shift_fn(s, B) if shift_fn else 0.0
        c = p + nr * lift + B * sh
        rows.append([c + B * w * (k / (across - 1) - 0.5) + nr * dome * math.sin(math.pi * k / (across - 1))
                     for k in range(across)])
    return grid_bm(rows, bm=bm)

def smooth_path(pts, it=3):
    for _ in range(it):
        pts = [pts[0]] + [(pts[i - 1] + pts[i] * 2 + pts[i + 1]) / 4 for i in range(1, len(pts) - 1)] + [pts[-1]]
    return pts

# collar bands. Wearer's-left panel is on top: its band runs from the right waist, over the right bust,
# through the crossing and up the left V edge. The right panel's band runs down the right V edge and
# tucks under at the crossing. A standing collar closes the loop around the back of the neck.
IT_BAND_W = 0.085

def surface_ribbon(bvh, pts, width, lift, dome=0.006, smooth=2, n=None):
    pts = resample(smooth_path(pts, smooth), n or len(pts))
    P, Nn = [], []
    for p in pts:
        q, nr = snap(bvh, p, 0.0)
        P.append(q); Nn.append(nr)
    return ribbon_bm(P, Nn, width if callable(width) else (lambda s: width), lift, across=3, dome=dome)

def standing_collar(mode, off, z0, height, lean, t0, t1, n=28, bm=None):
    rows = []
    for k in range(3):
        f = k / 2
        rr = []
        for j in range(n):
            t = t0 + (t1 - t0) * j / (n - 1)
            base = surf(t, z0, mode, off)
            radial = Vector((base.x, base.y - TY(z0), 0)).normalized()
            # ends taper down so the collar blends into the front bands
            e = min(j, n - 1 - j) / 4.0
            hh = height * min(1.0, 0.35 + 0.65 * e)
            rr.append(base + Vector((0, 0, hh * f)) + radial * (lean * f * f))
        rows.append(rr)
    return grid_bm(rows, bm=bm)

def front_point(x, z, mode, off):
    """point + normal on a garment surface at front coordinates (x, z) -- analytic, no snapping."""
    t = t_for_x(z, abs(x), mode, off)
    if x < 0:
        t = 180 - t
    p = surf(t, z, mode, off)
    a = surf(t + 0.4, z, mode, off) - surf(t - 0.4, z, mode, off)
    b = surf(t, z + 0.004, mode, off) - surf(t, z - 0.004, mode, off)
    n = b.cross(a).normalized()
    if n.y > 0:
        n = -n
    return p, n

def param_ribbon(xz, width, lift, mode, off, n, dome=0.004, bm=None):
    pts = resample([Vector((x, 0, z)) for x, z in xz], n)
    pts = smooth_path(pts, 3)
    P, Nn = zip(*[front_point(p.x, p.z, mode, off) for p in pts])
    return ribbon_bm(list(P), list(Nn), width if callable(width) else (lambda s: width), lift, bm=bm,
                     across=3, dome=dome)

# over panel: right waist -> over the right bust -> crossing -> up the left V edge
over_xz = [(-0.40 + 0.40 * f - 0.035 * math.sin(math.pi * f), 2.6 + (Z_CROSS - 2.6) * f ** 0.8) for f in [k / 14 for k in range(15)]]
over_xz += [(inner_gap(z) + IT_BAND_W * 0.42, z) for z in [Z_CROSS + (4.07 - Z_CROSS) * k / 14 for k in range(1, 15)]]
under_xz = [(-(inner_gap(z) + IT_BAND_W * 0.42), z) for z in [4.07 - (4.07 - Z_CROSS + 0.06) * k / 16 for k in range(17)]]
bm = param_ribbon(under_xz, IT_BAND_W, 0.006, "cloth", IT_OFF, 24)
param_ribbon(over_xz, IT_BAND_W, 0.016, "cloth", IT_OFF, 46, bm=bm)
standing_collar("cloth", IT_OFF + 0.008, 4.07, 0.06, 0.0, 28, -208, bm=bm)
fix_normals(bm)
it_collar = bm_to_obj(bm, "InnerTop_Collar", CREAM_TRIM)
solidify(it_collar, 0.01, offset=-1, even=False)
sharpen(it_collar)
skin(it_collar, w_torso)

# ---------------------------------------------------------------------------
# 6. layered sash + cord + side knot + healer pouch
# ---------------------------------------------------------------------------
parts = []
rows = [ring(z, "cloth", 0.058, 64) for z in [2.52 + 0.3 * k / 6 for k in range(7)]]
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Sash_Main", SASH); solidify(ob, 0.02); sharpen(ob); parts.append(ob)
rows = [ring(z, "cloth", 0.066, 64) for z in [2.485, 2.51, 2.535]]           # thin under-layer peeking below
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Sash_Under", SASH2); solidify(ob, 0.015); parts.append(ob)

rows = []
for k in range(5):
    rr = []
    for j in range(64):
        t = 360 * j / 64
        zc = 2.67 + 0.05 * math.cos(math.radians(t - 70))   # slanted second wrap
        z = zc - 0.05 + 0.1 * k / 4
        rr.append(surf(t, z, "cloth", 0.082 + 0.004 * math.sin(math.pi * k / 4)))
    rows.append(rr)
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Sash_Wrap", SASH2); solidify(ob, 0.016); sharpen(ob); parts.append(ob)

# gold cord along the slanted wrap's upper edge + knot and tassels at wearer's left front
cord_pts = [surf(t, 2.67 + 0.05 * math.cos(math.radians(t - 70)) + 0.062, "cloth", 0.1) for t in range(-12, 193, 4)]

def tube_bm(path, radius_fn, seg=8, bm=None, cap=True):
    bm = bm or bmesh.new()
    rows = []
    n = len(path)
    ref = Vector((0, 0, 1))
    for i in range(n):
        T = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        a = T.cross(ref)
        if a.length < 0.1:
            a = T.cross(Vector((1, 0, 0)))
        a.normalize(); b = T.cross(a).normalized()
        r = radius_fn(i / (n - 1))
        rows.append([path[i] + (a * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * r
                     for k in range(seg)])
    return grid_bm(rows, wrap=True, bm=bm, cap_start=cap, cap_end=cap)

bm = tube_bm(cord_pts, lambda s: 0.013, 8, cap=False)
kn = surf(64, 2.74, "cloth", 0.115)
bm_k = bmesh.new()
bmesh.ops.create_uvsphere(bm_k, u_segments=12, v_segments=8, radius=0.036)
for v in bm_k.verts:
    v.co = Vector((v.co.x * 1.2, v.co.y * 0.8, v.co.z)) + kn
tmp = bpy.data.meshes.new("t"); bm_k.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm_k.free()
for dx, L in ((-0.03, 0.42), (0.035, 0.34)):
    pth = catmull([kn + Vector((dx * 0.5, -0.01, -0.02)), kn + Vector((dx, -0.035, -L * 0.4)),
                   kn + Vector((dx * 1.3, -0.03, -L))], 6)
    tube_bm(pth, lambda s: 0.014, 8, bm=bm)
    tip = pth[-1]
    tas = [tip + Vector((0, 0, -0.01)), tip + Vector((0, -0.005, -0.1))]
    tube_bm(catmull(tas, 4), lambda s: 0.022 + 0.012 * s, 10, bm=bm)
fix_normals(bm)
ob = bm_to_obj(bm, "Sash_Cord", CORD); parts.append(ob)

# healer's pouch on the wearer's right hip
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.035, segments=3, affect="EDGES")
pc = surf(122, 2.4, "cloth", 0.13)
for v in bm.verts:
    v.co = Vector((v.co.x * 0.16, v.co.y * 0.09, v.co.z * 0.18)) + pc
fix_normals(bm, lambda c: pc)
pouch = bm_to_obj(bm, "Pouch", LEATHER)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.02, segments=2, affect="EDGES")
for v in bm.verts:
    v.co = Vector((v.co.x * 0.172, v.co.y * 0.1, v.co.z * 0.075)) + pc + Vector((0, -0.005, 0.058))
flap = bm_to_obj(bm, "PouchFlap", BOOT)
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.022)
for v in bm.verts:
    v.co += pc + Vector((0, -0.058, 0.025))
clasp = bm_to_obj(bm, "PouchClasp", GOLD)
sash = join(parts + [pouch, flap, clasp], "Sash")
sharpen(sash)
skin(sash, w_skirt)

# ---------------------------------------------------------------------------
# 7. outer coat -- ONE garment: body (open front, collar, lower panels w/ slits) + sleeves
# ---------------------------------------------------------------------------
C_OFF = 0.08
XE = Curve1D([(0.72, .58), (1.4, .5), (2.1, .43), (2.7, .39), (3.1, .42), (3.4, .45), (3.68, .42), (3.92, .33), (4.13, .24)])
SLIT_TOP = 1.55
HEM = 0.72

def coat_off(z):
    return C_OFF + 0.015 * sstep(2.6, 2.2, z)

zs_coat = [HEM + 0.06 * k for k in range(int((2.3 - HEM) / 0.06) + 1)] + zlist(2.36, 4.13, 0.06)
panels = [(None, 0.0, 15), (0.0, -90.0, 12), (-90.0, -180.0, 12), (-180.0, None, 15)]
coat_bm = bmesh.new()
for (ta, tb, ncol) in panels:
    rows = []
    for z in zs_coat:
        off = coat_off(z)
        d = 90 - t_for_x(z, XE(z), "coat", off)
        a = (90 - d) if ta is None else ta
        b = (-270 + d) if tb is None else tb
        gap = 2.6 * sstep(SLIT_TOP, HEM, z)          # slits open slightly toward the hem
        if ta is not None:
            a -= gap
        if tb is not None:
            b += gap
        rows.append([surf(a + (b - a) * j / (ncol - 1), z, "coat", off) for j in range(ncol)])
    grid_bm(rows, bm=coat_bm)
above = [v for v in coat_bm.verts if v.co.z > SLIT_TOP - 1e-3]
bmesh.ops.remove_doubles(coat_bm, verts=above, dist=2e-4)
fix_normals(coat_bm, axis_center)
COAT_BVH = BVHTree.FromBMesh(coat_bm)
coat_body = bm_to_obj(coat_bm.copy(), "Coat_Body", GREEN)
solidify(coat_body, 0.022)
skin(coat_body, w_skirt, bind=False)

# front trim: a broad dark band down each front edge + a standing collar round the back of the neck
TRIM_W = 0.12
fl = [front_hit(COAT_BVH, XE(z) + TRIM_W * 0.38, z)[0] for z in [HEM + 0.01 + (4.06 - HEM - 0.01) * k / 40 for k in range(41)]]
fr = [front_hit(COAT_BVH, -(XE(z) + TRIM_W * 0.38), z)[0] for z in [HEM + 0.01 + (4.06 - HEM - 0.01) * k / 40 for k in range(41)]]
wfn = lambda s: TRIM_W * (0.8 + 0.2 * sstep(0.0, 0.25, s)) * (1.0 + 0.25 * sstep(0.72, 1.0, s))  # tapers at the hem
bm = surface_ribbon(COAT_BVH, fl, wfn, 0.009, dome=0.005, n=46)
bm_r = surface_ribbon(COAT_BVH, fr, wfn, 0.009, dome=0.005, n=46)
tmp = bpy.data.meshes.new("t"); bm_r.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm_r.free()
standing_collar("coat", C_OFF + 0.01, 4.05, 0.12, 0.05, 36, -216, n=32, bm=bm)
seam = [surf(-90, z, "coat", coat_off(z)) for z in [SLIT_TOP + (4.02 - SLIT_TOP) * k / 30 for k in range(31)]]
bm_s = surface_ribbon(COAT_BVH, seam, 0.028, 0.005, dome=0.003, n=31)
tmp = bpy.data.meshes.new("t"); bm_s.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm_s.free()
fix_normals(bm)
coat_trim = bm_to_obj(bm, "Coat_Trim", GREEN_TRIM)
solidify(coat_trim, 0.02, even=False)
skin(coat_trim, w_skirt, bind=False)

# sleeves: cloth around a slim R15 arm. Set-in shoulder (inner side reaches toward the coat's shoulder),
# fuller upper sleeve, smooth taper to the cuff, rounded cross-section, sloped shoulder cap.
SW = Curve1D([(2.58, .272), (2.85, .292), (3.2, .335), (3.5, .355), (3.72, .345), (3.86, .318)])

def sleeve_ring(cx, z, h, n=28, e=2.3, flare=True):
    sg = 1 if cx > 0 else -1
    pts = []
    reach = 0.07 * sstep(3.5, 3.95, z)                   # shoulder side grows inward to meet the coat
    for j in range(n):
        a = 2 * math.pi * j / n
        c, s = math.cos(a), math.sin(a)
        hh = h * (1 + (0.018 * math.sin(5 * a + 0.7) * sstep(3.3, 2.7, z) if flare else 0))  # soft folds
        xl = hh * math.copysign(abs(c) ** (2 / e), c)
        if xl * sg < 0:
            xl -= sg * reach * (-xl * sg / hh)
        pts.append(Vector((cx + xl, -0.01 + (hh - 0.035) * math.copysign(abs(s) ** (2 / e), s), z)))
    return pts

def shoulder_slope(bm, cx):
    sg = 1 if cx > 0 else -1
    for v in bm.verts:
        if v.co.z > 3.7:
            outer = max(0.0, min(1.0, ((v.co.x - cx) * sg) / 0.4 * 0.5 + 0.5))
            v.co.z -= 0.08 * outer * sstep(3.7, 4.05, v.co.z)

sleeves = []
for cx in (ARM_CX, -ARM_CX):
    rows = [sleeve_ring(cx, z, SW(z)) for z in [2.58 + (3.86 - 2.58) * k / 13 for k in range(14)]]
    R = 0.17                                              # rounded shoulder cap (no flat box top)
    for k in range(1, 6):
        a = (math.pi / 2) * k / 5
        rows.append(sleeve_ring(cx, 3.86 + R * math.sin(a), SW(3.86) - R * (1 - math.cos(a)) ** 0.9))
    bm = grid_bm(rows, wrap=True, cap_end=True)
    shoulder_slope(bm, cx)
    fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
    ob = bm_to_obj(bm, "Sleeve", GREEN); solidify(ob, 0.022); skin(ob, w_arm, bind=False); sleeves.append(ob)
    # cuff band
    rows = [sleeve_ring(cx, z, SW(2.6) + 0.016 + 0.005 * math.sin(math.pi * k / 3), flare=False)
            for k, z in enumerate([2.565 + 0.1 * k / 3 for k in range(4)])]
    bm = grid_bm(rows, wrap=True)
    fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
    ob = bm_to_obj(bm, "Cuff", GREEN_TRIM); solidify(ob, 0.022); skin(ob, w_arm, bind=False); sleeves.append(ob)

coat = join([coat_body, coat_trim] + sleeves, "Coat")
sharpen(coat, 50)

bind_to_rig(coat)

# ---------------------------------------------------------------------------
# 8. wide-leg charcoal trousers, wrapped ankle guards, boots, hand/forearm wraps
# ---------------------------------------------------------------------------
parts = []
rows = [ring(z, "skin", 0.025, 40) for z in [1.9 + (2.56 - 1.9) * k / 6 for k in range(7)]]
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Pants_Hip", PANTS); solidify(ob, 0.025); skin(ob, lambda p: w_skirt(p, 0.8), bind=False); parts.append(ob)
PW = Curve1D([(0.64, .36), (0.72, .41), (0.9, .45), (1.25, .455), (1.65, .45), (2.1, .455)])
for cx in (LEG_CX, -LEG_CX):
    def leg_ring(z, h, n=28):
        pts = []
        for j in range(n):
            a = 2 * math.pi * j / n
            c, s = math.cos(a), math.sin(a)
            fold = 0.01 * math.sin(6 * a + cx * 3) * sstep(1.7, 0.9, z)   # soft vertical folds
            hh = h + fold
            pts.append(Vector((cx + hh * math.copysign(abs(c) ** (2 / 2.5), c),
                               0.0 + (hh - 0.02) * math.copysign(abs(s) ** (2 / 2.5), s), z)))
        return pts
    rows = [leg_ring(z, PW(z)) for z in [0.64 + (2.1 - 0.64) * k / 13 for k in range(14)]]
    bm = grid_bm(rows, wrap=True); fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
    ob = bm_to_obj(bm, "Pants_Leg", PANTS); solidify(ob, 0.02); skin(ob, w_leg, bind=False); parts.append(ob)
pants = join(parts, "Trousers")
sharpen(pants)
bind_to_rig(pants)

def band_rings(cx, cy, z0, z1, h, tilt, phase, n=24, bulge=0.012, e=4.0):
    rows = []
    for k in range(4):
        f = k / 3
        rr = []
        for j in range(n):
            a = 2 * math.pi * j / n
            c, s = math.cos(a), math.sin(a)
            hh = h + bulge * math.sin(math.pi * f)
            z = z0 + (z1 - z0) * f + tilt * math.cos(a + phase)
            rr.append(Vector((cx + hh * math.copysign(abs(c) ** (2 / e), c),
                              cy + (hh - 0.01) * math.copysign(abs(s) ** (2 / e), s), z)))
        rows.append(rr)
    return rows

parts = []
for cx in (LEG_CX, -LEG_CX):
    for k in range(4):
        z0 = 0.3 + k * 0.088
        bm = grid_bm(band_rings(cx, 0.0, z0, z0 + 0.1, 0.33 + 0.008 * k, 0.014 * (1 if k % 2 else -1),
                                cx * 2, bulge=0.006, e=3.4), wrap=True)          # tapers toward the ankle
        fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
        ob = bm_to_obj(bm, "AnkleWrap", WRAP); solidify(ob, 0.012); parts.append(ob)
wraps_leg = join(parts, "AnkleGuards")
sharpen(wraps_leg)
skin(wraps_leg, w_leg)

parts = []
for cx in (ARM_CX, -ARM_CX):
    for k, (z0, z1, h) in enumerate([(2.03, 2.19, 0.29), (2.19, 2.37, 0.292), (2.37, 2.6, 0.278)]):
        bm = grid_bm(band_rings(cx, 0.0, z0, z1, h, 0.008 * (1 if k % 2 else -1), 1.0, e=8.0, bulge=0.007), wrap=True)
        fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
        ob = bm_to_obj(bm, "HandWrap", WRAP); solidify(ob, 0.012); parts.append(ob)
wraps_arm = join(parts, "HandWraps")
sharpen(wraps_arm)
skin(wraps_arm, lambda p: {side(p.x) + ("Hand" if p.z < 2.295 else "LowerArm"): 1.0})

parts = []
for cx in (LEG_CX, -LEG_CX):
    for (cy, cz, sx, sy, sz, bev, m) in [(-0.07, 0.19, 0.345, 0.49, 0.15, 0.1, BOOT),
                                          (-0.075, 0.03, 0.36, 0.51, 0.032, 0.03, SOLE)]:
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1, use_grid_fill=True)
        for v in bm.verts:
            v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > 0.5],
                        offset=bev, segments=3, affect="EDGES", profile=0.5)
        for v in bm.verts:
            if v.co.y < 0 and v.co.z > 0 and m is BOOT:           # rounded, lower toe
                v.co.z -= 0.06 * (-v.co.y / sy) ** 2
            v.co += Vector((cx, cy, cz))
        fix_normals(bm, lambda c, cx=cx, cy=cy, cz=cz: Vector((cx, cy, cz)))
        parts.append(bm_to_obj(bm, "Boot", m))
    # strap across the instep
    bm = grid_bm(band_rings(cx, -0.1, 0.18, 0.24, 0.36, 0.045, -math.pi / 2, e=3.0), wrap=True)
    fix_normals(bm, lambda c, cx=cx: Vector((cx, -0.1, c.z)))
    ob = bm_to_obj(bm, "BootStrap", SOLE); solidify(ob, 0.015); parts.append(ob)
boots = join(parts, "Boots")
sharpen(boots, 40)
skin(boots, lambda p: {side(p.x) + "Foot": 1.0})

# ---------------------------------------------------------------------------
# 9. hair: auburn cap, swept fringe, high coiled bun, long loose side lock, gold ornament
# ---------------------------------------------------------------------------
def phi_max(theta):
    t = math.radians(theta)
    return 98 - 50 * math.cos(t) - 3 * math.cos(2 * t)

rows = []
for i in range(21):
    s = i / 20
    rr = []
    for j in range(60):
        th = 360 * j / 60
        ph = s * phi_max(th)
        back = 0.5 - 0.5 * math.cos(math.radians(th))
        off = 0.006 + (0.13 + 0.05 * back) * (1 - s ** 3.5)        # fuller crown, more volume at the back
        rr.append(head_P(th, ph, off))
    rows.append(rr)
bm = grid_bm(rows, wrap=True)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
fix_normals(bm, lambda c: HC)
hair_parts = [bm_to_obj(bm, "HairCap", HAIR)]

def lock_bm(ctrl, w0, th0, out_fn, n=14, seg=8, wprof=None, bm=None):
    pts = resample(catmull(ctrl, 10), n)
    bm = bm or bmesh.new()
    rows = []
    for i in range(n - 1):
        s = i / (n - 1)
        p = pts[i]
        T = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        o = out_fn(p); o = (o - T * o.dot(T)).normalized()
        B = T.cross(o).normalized()
        w = w0 * (wprof(s) if wprof else (1 - s ** 2.0) ** 0.75 * (0.9 + 0.2 * math.sin(math.pi * s)))
        w *= 0.55 + 0.45 * sstep(0.0, 0.18, s)          # narrow, buried root: no blunt tube ends
        th = th0 * (1 - s ** 1.6) ** 0.8 + 0.004
        rr = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            c, sn = math.cos(a), math.sin(a)
            # lens section with a slight outward ridge
            rr.append(p + B * (w * 0.5 * c) + o * (th * 0.5 * sn * (1 + 0.25 * sn)))
        rows.append(rr)
    tip = pts[-1]
    V = [[bm.verts.new(q) for q in r] for r in rows]
    for i in range(len(V) - 1):
        for k in range(seg):
            bm.faces.new((V[i][k], V[i][(k + 1) % seg], V[i + 1][(k + 1) % seg], V[i + 1][k]))
    tv = bm.verts.new(tip)
    for k in range(seg):
        bm.faces.new((V[-1][k], V[-1][(k + 1) % seg], tv))
    rv = bm.verts.new(pts[0])
    for k in range(seg):
        bm.faces.new((V[0][(k + 1) % seg], V[0][k], rv))
    return bm

head_out = lambda p: (p - HC)
def on_head(theta, phi, off):
    return head_P(theta, phi, off)

hair_bm = bmesh.new()
# A few strong anime masses instead of many clumps. (theta, phi, offset) control points; roots buried.
FRINGE = [
    ([(28, 6, .08), (14, 30, .185), (-10, 54, .15), (-34, 71, .085), (-54, 83, .04)], .54, .13),   # main sweep
    ([(46, 12, .08), (38, 36, .165), (22, 58, .115), (8, 71, .05)], .38, .11),                      # second layer
    ([(64, 20, .07), (64, 46, .135), (58, 66, .085), (52, 79, .04)], .28, .09),                     # left fringe
    ([(-40, 26, .08), (-70, 52, .15), (-88, 84, .1), (-92, 112, .055), (-88, 136, .02)], .32, .1),  # right frame
    ([(80, 30, .07), (90, 62, .115), (94, 94, .075), (91, 122, .045), (86, 142, .02)], .26, .085),  # left frame
]
for ctrl, w0, th0 in FRINGE:
    lock_bm([on_head(a, b, o) for a, b, o in ctrl], w0, th0, head_out, n=16, bm=hair_bm)

# sides + back: broad masses swept up into the bun (strong side / back silhouette)
for th in (112, 138, 162, 198, 222, 248):
    pm = phi_max(th)
    ctrl = [on_head(th, pm - 4, .02), on_head(th + (180 - th) * 0.22, pm - 30, .1),
            on_head(th + (180 - th) * 0.55, 72, .15), on_head(180 + (th - 180) * 0.12, 38, .14)]
    lock_bm(ctrl, 0.34, 0.085, head_out, n=16, bm=hair_bm,
            wprof=lambda s: (0.6 + 0.4 * sstep(0.0, 0.25, s)) * (1 - s ** 3) ** 0.7)
# subtle layered strands escaping at the nape
for th, L, w0 in [(158, 22, .2), (180, 28, .22), (202, 22, .2)]:
    pm = phi_max(th)
    ctrl = [on_head(th, pm - 30, .03), on_head(th, pm - 6, .07), on_head(th + (180 - th) * 0.15, pm + L, .03)]
    lock_bm(ctrl, w0, 0.06, head_out, bm=hair_bm)

# one elegant long strand (wearer's right): over the shoulder, gentle S-curve down the coat front
top = [on_head(-96, 56, .07), on_head(-104, 92, .1), on_head(-108, 118, .09)]
low = []
for x, z, lift in [(-0.5, 3.98, 0.14), (-0.56, 3.76, 0.09), (-0.53, 3.52, 0.075), (-0.58, 3.27, 0.07)]:
    loc, nr = front_hit(COAT_BVH, x, z)
    low.append(loc + nr * lift)

def side_out(p):
    if p.z > 4.1:
        return p - HC
    loc, nr, _, _ = COAT_BVH.find_nearest(p)
    return nr
lock_bm(top + low, 0.2, 0.075, side_out, n=26, seg=8,
        wprof=lambda s: (1 - s ** 2.2) ** 0.8 * (0.8 + 0.3 * math.sin(math.pi * s)), bm=hair_bm)
fix_normals(hair_bm)
hair_parts.append(bm_to_obj(hair_bm, "HairLocks", HAIR))

# high coiled bun
bun_dir = head_dir(180, 30)
bun_c = HC + bun_dir * 0.8 + Vector((0, 0, 0.05))
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=1.0)
up = bun_dir.normalized()
rot = up.to_track_quat("Z", "Y").to_matrix()
for v in bm.verts:
    v.co = rot @ Vector((v.co.x * 0.2, v.co.y * 0.19, v.co.z * 0.17)) + bun_c
fix_normals(bm, lambda c: bun_c)
hair_parts.append(bm_to_obj(bm, "HairBun", HAIR))
# coil wrapped around the bun
coil = []
for k in range(60):
    f = k / 59
    a = 2 * math.pi * 1.8 * f
    r = 0.215 - 0.1 * f
    h = -0.09 + 0.19 * f
    coil.append(bun_c + rot @ Vector((r * math.cos(a), r * math.sin(a), h)))
bm = lock_bm(coil[::3], 0.2, 0.12, lambda p: (p - bun_c), n=44, seg=10,
             wprof=lambda s: (1 - s ** 3) ** 0.6)
fix_normals(bm)
hair_parts.append(bm_to_obj(bm, "HairCoil", HAIR))
# two tufts flicking out of the bun: gives the back / side silhouette its identity
bm = bmesh.new()
for sx, k in ((1, 1.0), (-1, 0.78)):
    p0 = bun_c + up * 0.06
    ctrl = [p0, p0 + Vector((sx * 0.09, 0.17, 0.13)) * k, p0 + Vector((sx * 0.19, 0.36, 0.08)) * k,
            p0 + Vector((sx * 0.24, 0.47, -0.08)) * k]
    lock_bm(ctrl, 0.17 * k, 0.075, lambda p: Vector((0, 0, 1)), n=14, bm=bm,
            wprof=lambda s: (0.6 + 0.4 * sstep(0.0, 0.2, s)) * (1 - s ** 1.8) ** 0.8)
fix_normals(bm)
hair_parts.append(bm_to_obj(bm, "HairTufts", HAIR))
hair = join(hair_parts, "Hair")
skin(hair, lambda p: {"Head": 1.0} if p.z > 4.12 or abs(p.x) < 0.5
     else {"Head": sstep(3.4, 4.12, p.z), "UpperTorso": 1 - sstep(3.4, 4.12, p.z)})

# gold ornament: band round the bun base + hairpin with a jade-centred flower and dangling beads
parts = []
bm = bmesh.new()
ring_c = bun_c - up * 0.1
rr_pts = [ring_c + rot @ Vector((0.215 * math.cos(2 * math.pi * k / 40), 0.205 * math.sin(2 * math.pi * k / 40), 0))
          for k in range(41)]
tube_bm(rr_pts, lambda s: 0.026, 10, bm=bm, cap=False)
fix_normals(bm); parts.append(bm_to_obj(bm, "OrnRing", GOLD))
pin_a = bun_c + rot @ Vector((-0.42, 0.05, 0.06))
pin_b = bun_c + rot @ Vector((0.40, -0.03, -0.02))
bm = tube_bm([pin_a.lerp(pin_b, k / 10) for k in range(11)], lambda s: 0.018 * (1 - 0.6 * s), 8)
fix_normals(bm); parts.append(bm_to_obj(bm, "OrnPin", GOLD))
fl_c = pin_a + (pin_a - pin_b).normalized() * 0.02
fl_n = (pin_a - pin_b).normalized()
fq = fl_n.to_track_quat("Z", "Y").to_matrix()
bm = bmesh.new()
rowsf = []
for i in range(3):
    rr = []
    for k in range(60):
        a = 2 * math.pi * k / 60
        R = (0.06 + 0.035 * abs(math.cos(3 * a)) ** 0.7) * (1 - i * 0.45)
        rr.append(fl_c + fq @ Vector((R * math.cos(a), R * math.sin(a), 0.012 * i)))
    rowsf.append(rr)
grid_bm(rowsf, wrap=True, bm=bm, cap_end=True)
bm2 = grid_bm([[fl_c + fq @ Vector((q.x, q.y, -0.01)) for q in [fq.inverted() @ (p - fl_c) for p in rowsf[0]]]] +
              [[fl_c + fq @ Vector((0, 0, -0.012))] * 60], wrap=True)
tmp = bpy.data.meshes.new("t"); bm2.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm2.free()
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
fix_normals(bm); parts.append(bm_to_obj(bm, "OrnFlower", GOLD))
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.034)
for v in bm.verts:
    v.co = fq @ Vector((v.co.x, v.co.y, v.co.z * 0.6)) + fl_c + fl_n * 0.03
parts.append(bm_to_obj(bm, "OrnJade", JADE))
bm = bmesh.new()
for k in range(3):
    c = fl_c + Vector((0.0, 0.0, -0.1 - 0.075 * k)) + fl_n * 0.01
    tmpb = bmesh.new()
    bmesh.ops.create_uvsphere(tmpb, u_segments=10, v_segments=6, radius=0.022 - 0.004 * k)
    for v in tmpb.verts:
        v.co += c
    tmp = bpy.data.meshes.new("t"); tmpb.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); tmpb.free()
tube_bm([fl_c + Vector((0, 0, -0.04)), fl_c + Vector((0, 0, -0.26))], lambda s: 0.004, 6, bm=bm)
parts.append(bm_to_obj(bm, "OrnBeads", GOLD))
orn = join(parts, "HairOrnament")
skin(orn, w_rigid("Head"))

# ---------------------------------------------------------------------------
# tidy up + metadata
# ---------------------------------------------------------------------------
order = ["Body_Torso", "Body_Limbs", "Head_Mesh", "Face_Features", "InnerTop", "InnerTop_Collar", "Sash",
         "Coat", "Trousers", "AnkleGuards", "Boots", "HandWraps", "Hair", "HairOrnament"]
tris = {}
for name in order:
    ob = bpy.data.objects[name]
    ob["hb_unit"] = "HealerBrawler"
    tris[name] = sum(len(p.vertices) - 2 for p in ob.data.polygons)
ARM["hb_template"] = "HealerBrawler v2 -- R15 foundation + custom anime geometry (silhouette pass)"
print("TRIS", tris, "TOTAL", sum(tris.values()))

txt = bpy.data.texts.new("build_healer_brawler_v2.py")
txt.from_string(open(os.path.abspath(__file__)).read())

# neutral stage for opening the file
sc = bpy.context.scene
sc.render.engine = "CYCLES"
bpy.ops.wm.save_as_mainfile(filepath=OUT_PATH, compress=True)
print("SAVED", OUT_PATH)
