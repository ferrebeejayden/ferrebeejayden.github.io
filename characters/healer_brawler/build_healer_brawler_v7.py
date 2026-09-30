"""
Healer / Brawler unit v7 -- bust + clothing-fit correction on v6 (build_healer_brawler_v6.py unchanged):
two real ellipsoid bust volumes smooth-unioned onto the block torso, wrap top follows them at a thinner
offset with a kept centre separation, robe front edges open outward at chest height. All else = v6.

Healer / Brawler unit v6 -- HAIR-ONLY rebuild on the approved v5 body (build_healer_brawler_v5.py unchanged).
Everything except the hair meshes and the hair shader is identical to v5.

Healer / Brawler unit v5 -- ROBLOX-FIRST style correction.
Roblox avatar first, anime second: full-size blocky R15 limbs, boxy torso with broad square shoulders,
stylised bust integrated onto the block, boxy flared sleeves built around the 1x1 arms, rounded-cube
Roblox head with large anime eyes, chunky faceted anime hair. Rig / weighting / pose tests / materials
carried over from v3 (build_healer_brawler_v3.py, kept unchanged).

Healer / Brawler unit v3 -- shoulder connection, feminine hair rebuild, material depth.
Built on the approved v2 proportions (build_healer_brawler_v2.py, kept unchanged).

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

def soften(ob, width=0.005, segs=1, angle=62):
    """consistent small bevels on garment rims + weighted normals, so edges stop reading as raw primitives."""
    b = ob.modifiers.new("Bevel", "BEVEL")
    b.width = width; b.segments = segs; b.limit_method = "ANGLE"; b.angle_limit = math.radians(angle)
    b.harden_normals = False
    wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    wn.keep_sharp = True; wn.weight = 60
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

def w_torso(p, arm_blend=0.35, neck=True):
    """torso-attached geometry: Lower/UpperTorso split at the waist, shoulders feed into the arm."""
    up = sstep(2.45, 2.95, p.z)
    w = {"UpperTorso": up, "LowerTorso": 1 - up}
    a = sstep(0.86, 1.02, abs(p.x)) * sstep(3.85, 4.02, p.z) * arm_blend
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

def w_arm(p, torso_blend=0.3):
    s = side(p.x)
    lo = sstep(3.3, 2.95, p.z)
    w = {s + "UpperArm": 1 - lo, s + "LowerArm": lo}
    t = sstep(1.1, 0.95, abs(p.x)) * sstep(3.85, 4.1, p.z) * torso_blend   # shoulder corner eases into the torso
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
GREEN_SEAM = mat("Coat_Seam", srgb(30, 50, 38), rough=0.8, sheen=0.3)
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

ARM_CX = 1.50     # Roblox arm centre (1x1 blocks, unchanged)
LEG_CX = 0.50     # Roblox leg centre (1x1 blocks, unchanged)

# ---------------------------------------------------------------------------
# 1. parametric torso surface (the shared body the garments are offset from)
# ---------------------------------------------------------------------------
TW = Curve1D([(1.8, .97), (2.2, .98), (2.5, .93), (2.78, .86), (3.05, .9), (3.4, .97), (3.75, .99),
              (3.94, .99), (4.0, .95), (4.04, .8), (4.07, .5), (4.1, .26), (4.2, .21), (4.5, .2)])
TD = Curve1D([(1.8, .5), (2.2, .5), (2.5, .48), (2.78, .45), (3.05, .46), (3.4, .48), (3.75, .49),
              (3.94, .49), (4.0, .46), (4.04, .4), (4.07, .3), (4.1, .22), (4.2, .2), (4.5, .19)])
TN = Curve1D([(1.8, 5.0), (2.5, 4.5), (2.78, 4.0), (3.4, 4.6), (3.94, 5.0), (4.04, 3.5), (4.1, 2.2), (4.2, 2.0), (4.5, 2.0)])
TY = Curve1D([(1.8, .0), (4.5, .02)])

# robe: follows the block torso, pinches a little at the sash, flares to the hem
CW = Curve1D([(0.85, 1.18), (1.3, 1.12), (1.8, 1.07), (2.35, 1.03), (2.78, .95), (3.05, .93), (3.4, .97), (3.75, .99),
              (3.94, .99), (4.0, .95), (4.04, .8), (4.07, .5), (4.1, .26), (4.2, .21), (4.5, .2)])
CD = Curve1D([(0.85, .63), (1.3, .6), (1.8, .58), (2.35, .57), (2.78, .55), (3.05, .5), (3.4, .48), (3.75, .49),
              (3.94, .49), (4.0, .46), (4.04, .4), (4.07, .3), (4.1, .22), (4.2, .2), (4.5, .19)])

# Bust: two real rounded ellipsoid volumes unioned onto the block torso (v7).
# Each form ~0.86 studs across, ~0.48 studs forward projection, meeting at the centre line.
BUST = dict(cx=.41, cz=3.34, cy=-.44, rx=.43, ry=.52, rzu=.42, rzd=.37)
# smooth-union radii: K_T = blend into the torso (underside tuck), K_C = blend between the two forms
K_T = {"skin": 0.04, "cloth": 0.07, "coat": 0.14}
K_C = {"skin": 0.012, "cloth": 0.07, "coat": 0.16}

def smin(a, b, k):
    """polynomial smooth minimum (more negative y = further forward)."""
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25

def ell_front(x, z, side):
    B = BUST
    dx = (x - side * B["cx"]) / B["rx"]
    dz = (z - B["cz"]) / (B["rzu"] if z > B["cz"] else B["rzd"])
    q = 1.0 - dx * dx - dz * dz
    return B["cy"] + TY(z) - B["ry"] * math.sqrt(max(q, 0.0))

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
        forms = smin(ell_front(x, z, 1), ell_front(x, z, -1), K_C[mode])
        y = y + (smin(y, forms, K_T[mode]) - y) * sstep(0.0, 0.35, s)
    return Vector((x, y, z))

def underarm(p, off):
    """flatten every layer's side where the blocky arm hangs, so sleeve and body meet cleanly."""
    lim = 0.93 + off * 0.5
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
rows = [ring(z, "skin", 0.0, 76) for z in zlist(2.02, 4.47, 0.05)]
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
    k = {"UpperArm": 0.92, "LowerArm": 0.96, "Hand": 0.97, "UpperLeg": 0.9, "LowerLeg": 0.9, "Foot": 0.88}
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
            v.co.z = min(v.co.z, 4.0)          # stays inside the sleeve top
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
HC = Vector((0.0, -0.01, 4.63))
FZ = HC.z - 4.60
HR = Vector((0.6, 0.59, 0.6))
HN = 3.3

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
        p.x *= 1 - 0.08 * k ** 2          # Roblox head: only a hint of a softer jaw
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

EYE_Z = 4.53
for ex in (-0.2, 0.2):
    o = 1 if ex > 0 else -1
    W = lambda u, v: (ex + o * u, EYE_Z + v)
    # large Roblox-anime eye: tall, slightly lifted outer corner
    upper = bez((-0.085, 0.02), (-0.06, 0.12), (0.06, 0.135), (0.112, 0.07), 18)
    lower = bez((-0.085, 0.02), (-0.07, -0.085), (0.07, -0.1), (0.112, 0.07), 18)
    sclera = [W(*p) for p in upper] + [W(*p) for p in reversed(lower[1:-1])]
    if o < 0:
        sclera.reverse()
    add_poly(sclera, W(0.012, 0.015), 0.003, "sclera")

    def ellipse(cu, cv, ru, rv, n=30, pad=0.004):
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            u, v = cu + ru * math.cos(a), cv + rv * math.sin(a)
            u = max(-0.08, min(0.108, u))
            v = min(v, interp_v(upper, u) - pad)
            v = max(v, interp_v(lower, u) + pad * 0.5)
            pts.append(W(u, v))
        if o < 0:
            pts.reverse()
        return pts
    add_poly(ellipse(0.012, 0.0, 0.072, 0.1), W(0.012, 0.0), 0.005, "iris")
    add_poly(ellipse(0.012, -0.018, 0.06, 0.074), W(0.012, -0.018), 0.007, "gold")
    add_poly(ellipse(0.012, 0.055, 0.068, 0.04, 22, 0.002), W(0.012, 0.05), 0.008, "iris")      # lid shadow
    add_poly(ellipse(0.012, -0.004, 0.026, 0.05), W(0.012, -0.004), 0.009, "pupil")
    add_poly(ellipse(-0.02, 0.035, 0.024, 0.03, 16, 0.0), W(-0.02, 0.035), 0.011, "hi")
    add_poly(ellipse(0.04, -0.05, 0.012, 0.011, 12, 0.0), W(0.04, -0.05), 0.011, "hi")
    lash = upper + [(0.13, 0.09), (0.148, 0.106)]
    n = len(lash)
    widths = [0.012 + 0.02 * sstep(0.0, 0.5, i / (n - 3)) for i in range(n - 2)] + [0.016, 0.0]
    add_stroke([W(*p) for p in lash], widths, 0.012, "lash", align=o * 1.0)
    low = [W(*p) for p in lower[10:]]
    add_stroke(low, [0.0] + [0.007] * (len(low) - 2) + [0.0], 0.005, "lid")
    brow = catmull([W(-0.07, 0.19), W(0.02, 0.215), W(0.1, 0.2)], 6)
    bw = [0.016 - 0.012 * (i / (len(brow) - 1)) ** 1.2 for i in range(len(brow))]
    add_stroke([(p.x, p.y) for p in brow], bw, 0.004, "brow")
    for k in range(2):
        cx = ex + o * (0.035 + 0.035 * k)
        add_stroke([(cx - o * 0.009, 4.39), (cx + o * 0.013, 4.415)], [0.006, 0.006], 0.003, "blush")

add_stroke([(0.006, 4.418), (-0.004, 4.41)], [0.006, 0.006], 0.003, "nose")                     # tiny nose mark
mouth = catmull([(-0.05, 4.33), (-0.015, 4.318), (0.025, 4.32), (0.058, 4.338)], 8)             # small confident smile
mw = [0.004 + 0.007 * math.sin(math.pi * i / (len(mouth) - 1)) for i in range(len(mouth))]
add_stroke([(p.x, p.y) for p in mouth], mw, 0.004, "mouth")

face = bm_to_obj(face_bm, "Face_Features", [FACE_M[k] for k in FACE_KEYS])
skin(head, w_rigid("Head"))
skin(face, w_rigid("Head"))

# ---------------------------------------------------------------------------
# 5. cream wrapped inner top (crossed lapels over the bust)
# ---------------------------------------------------------------------------
IT_OFF = 0.022                       # thinner: the body shape stays readable through the wrap
Z_CROSS = 3.0                        # lapels follow the inner curve of each form and cross just above the sash
GAP = Curve1D([(Z_CROSS, 0.0), (3.25, 0.05), (3.55, 0.11), (3.85, 0.19), (4.13, 0.28)])

def inner_gap(z):
    return 0.0 if z <= Z_CROSS else GAP(z)

rows = []
N_IT = 84
zs_it = zlist(2.46, 4.13, 0.045)
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
solidify(inner_top, 0.02)
soften(inner_top, 0.004)
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
IT_BAND_W = 0.13

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

def param_ribbon(xz, width, lift, mode, off, n, dome=0.004, bm=None, across=5):
    """ribbon whose every vertex sits on the analytic garment surface (hugs concave/convex curves)."""
    pts = resample([Vector((x, 0, z)) for x, z in xz], n)
    pts = smooth_path(pts, 3)
    rows = []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
        d = Vector((d.x, d.z)).normalized()
        perp = Vector((-d.y, d.x))
        rr = []
        for k in range(across):
            f = k / (across - 1) - 0.5
            q, nr = front_point(p.x + perp.x * width * f, p.z + perp.y * width * f, mode, off)
            rr.append(q + nr * (lift + dome * math.cos(math.pi * f)))
        rows.append(rr)
    return grid_bm(rows, bm=bm)

# over panel: right waist -> over the right bust -> crossing -> up the left V edge
over_xz = [(-0.2 + 0.2 * f, 2.72 + (Z_CROSS - 2.72) * f) for f in [k / 6 for k in range(7)]]
over_xz += [(inner_gap(z) + IT_BAND_W * 0.42, z) for z in [Z_CROSS + (4.07 - Z_CROSS) * k / 30 for k in range(1, 31)]]
under_xz = [(-(inner_gap(z) + IT_BAND_W * 0.42), z) for z in [4.07 - (4.07 - Z_CROSS + 0.06) * k / 16 for k in range(17)]]
bm = param_ribbon(under_xz, IT_BAND_W, 0.008, "cloth", IT_OFF, 48, dome=0.008)
param_ribbon(over_xz, IT_BAND_W, 0.018, "cloth", IT_OFF, 60, bm=bm, dome=0.008)
standing_collar("cloth", IT_OFF + 0.01, 4.07, 0.08, 0.0, 28, -208, bm=bm)
fix_normals(bm)
it_collar = bm_to_obj(bm, "InnerTop_Collar", CREAM_TRIM)
solidify(it_collar, 0.026, offset=-1, even=False)
soften(it_collar, 0.004)
sharpen(it_collar)
skin(it_collar, w_torso)

# ---------------------------------------------------------------------------
# 6. layered sash + cord + side knot + healer pouch
# ---------------------------------------------------------------------------
parts = []
rows = [ring(z, "cloth", 0.075, 64) for z in [2.5 + 0.42 * k / 7 for k in range(8)]]
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Sash_Main", SASH); solidify(ob, 0.035); sharpen(ob); parts.append(ob)
rows = [ring(z, "cloth", 0.09, 64) for z in [2.45, 2.49, 2.53]]           # thin under-layer peeking below
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Sash_Under", SASH2); solidify(ob, 0.025); parts.append(ob)

rows = []
for k in range(5):
    rr = []
    for j in range(64):
        t = 360 * j / 64
        zc = 2.7 + 0.06 * math.cos(math.radians(t - 70))   # slanted second wrap
        z = zc - 0.075 + 0.15 * k / 4
        rr.append(surf(t, z, "cloth", 0.112 + 0.006 * math.sin(math.pi * k / 4)))
    rows.append(rr)
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Sash_Wrap", SASH2); solidify(ob, 0.028); sharpen(ob); parts.append(ob)

# gold cord along the slanted wrap's upper edge + knot and tassels at wearer's left front
cord_pts = [surf(t, 2.7 + 0.06 * math.cos(math.radians(t - 70)) + 0.09, "cloth", 0.135) for t in range(-12, 193, 4)]

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

bm = tube_bm(cord_pts, lambda s: 0.018, 8, cap=False)
kn = surf(64, 2.78, "cloth", 0.16)
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
pc = surf(122, 2.38, "cloth", 0.17)
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
end_xz = [(0.44 - 0.02 * f, 2.72 - 0.56 * f) for f in [k / 10 for k in range(11)]]
bm = bmesh.new()
rows = []
for x, z in end_xz:
    p, n = front_point(x, z, "cloth", 0.14 if z > 2.48 else 0.08)
    w = 0.15 * (1 - 0.35 * sstep(2.3, 2.16, z))
    rows.append([p + n * 0.02 + Vector((-w / 2 + w * k / 2, 0, 0)) + n * 0.006 * math.sin(math.pi * k / 2) for k in range(3)])
rows.append([Vector((end_xz[-1][0], rows[-1][1].y, end_xz[-1][1] - 0.06))] * 3)       # pointed end
grid_bm(rows, bm=bm)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
fix_normals(bm)
tail = bm_to_obj(bm, "Sash_End", SASH); solidify(tail, 0.018)
sash = join(parts + [pouch, flap, clasp, tail], "Sash")
soften(sash, 0.004)
sharpen(sash)
skin(sash, w_skirt)

# ---------------------------------------------------------------------------
# 7. outer coat -- ONE garment: body (open front, collar, lower panels w/ slits) + sleeves
# ---------------------------------------------------------------------------
C_OFF = 0.075
XE = Curve1D([(0.88, .6), (1.6, .52), (2.2, .45), (2.72, .41), (2.95, .5), (3.2, .7), (3.45, .78), (3.7, .73), (3.9, .58), (4.05, .4), (4.13, .3)])
SLIT_TOP = 1.7
HEM = 0.88

def coat_off(z):
    return C_OFF + 0.015 * sstep(2.6, 2.2, z)

zs_coat = [HEM + 0.08 * k for k in range(int((2.3 - HEM) / 0.08) + 1)] + zlist(2.36, 4.13, 0.05)
panels = [(None, 0.0, 18), (0.0, -90.0, 12), (-90.0, -180.0, 12), (-180.0, None, 18)]
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
        rr = []
        for j in range(ncol):
            t = a + (b - a) * j / (ncol - 1)
            p = surf(t, z, "coat", off)
            fold = 0.022 * math.sin(math.radians(t) * 9 + 0.6) * sstep(2.3, 1.3, z)   # a few large skirt folds
            p += Vector((p.x, p.y - TY(z), 0)).normalized() * fold
            rr.append(p)
        rows.append(rr)
    grid_bm(rows, bm=coat_bm)
above = [v for v in coat_bm.verts if v.co.z > SLIT_TOP - 1e-3]
bmesh.ops.remove_doubles(coat_bm, verts=above, dist=2e-4)
fix_normals(coat_bm, axis_center)
COAT_BVH = BVHTree.FromBMesh(coat_bm)
_fb = coat_bm.copy(); _tmp = bpy.data.meshes.new('t'); IT_BM.to_mesh(_tmp); _fb.from_mesh(_tmp); bpy.data.meshes.remove(_tmp)
FRONT_BVH = BVHTree.FromBMesh(_fb)
HEM_ROWS = []
coat_body = bm_to_obj(coat_bm.copy(), "Coat_Body", GREEN)
solidify(coat_body, 0.03)
skin(coat_body, w_skirt, bind=False)

# front trim: a broad dark band down each front edge + a standing collar round the back of the neck
TRIM_W = 0.17
fl = [front_hit(COAT_BVH, XE(z) + TRIM_W * 0.38, z)[0] for z in [HEM + 0.01 + (4.06 - HEM - 0.01) * k / 80 for k in range(81)]]
fr = [front_hit(COAT_BVH, -(XE(z) + TRIM_W * 0.38), z)[0] for z in [HEM + 0.01 + (4.06 - HEM - 0.01) * k / 80 for k in range(81)]]
wfn = lambda s: TRIM_W * (0.8 + 0.2 * sstep(0.0, 0.25, s)) * (1.0 + 0.25 * sstep(0.72, 1.0, s))  # tapers at the hem
bm = surface_ribbon(COAT_BVH, fl, wfn, 0.009, dome=0.005, smooth=4, n=96)
bm_r = surface_ribbon(COAT_BVH, fr, wfn, 0.009, dome=0.005, smooth=4, n=96)
tmp = bpy.data.meshes.new("t"); bm_r.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm_r.free()
standing_collar("coat", C_OFF + 0.012, 4.05, 0.14, 0.05, 36, -216, n=32, bm=bm)
seam = [surf(-90, z, "coat", coat_off(z)) for z in [SLIT_TOP + (4.02 - SLIT_TOP) * k / 30 for k in range(31)]]
bm_s = surface_ribbon(COAT_BVH, seam, 0.028, 0.005, dome=0.003, n=31)
tmp = bpy.data.meshes.new("t"); bm_s.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm_s.free()
# side seams (darker ridge from the underarm to the slit top)
for tt in (0.0, -180.0):
    sp = [surf(tt, z, "coat", coat_off(z)) for z in [SLIT_TOP + (3.62 - SLIT_TOP) * k / 22 for k in range(23)]]
    bm_s = surface_ribbon(COAT_BVH, sp, 0.022, 0.004, dome=0.004, n=23)
    tmp = bpy.data.meshes.new("t"); bm_s.to_mesh(tmp); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp); bm_s.free()
fix_normals(bm)
coat_trim = bm_to_obj(bm, "Coat_Trim", GREEN_TRIM)
solidify(coat_trim, 0.032, even=False)
skin(coat_trim, w_skirt, bind=False)

# sleeves: a custom clothing shell around the blocky Roblox arm -- rounded-box section, square shoulder top
# with a soft edge, slight flare to a strong cuff, gold stripe trim.
SW = Curve1D([(2.46, .68), (2.7, .63), (3.1, .585), (3.6, .565), (4.0, .56)])

def sleeve_ring(cx, z, h, n=32, e=5.0, flare=True):
    pts = []
    for j in range(n):
        a = 2 * math.pi * j / n
        c, s = math.cos(a), math.sin(a)
        hh = h * (1 + (0.02 * math.sin(4 * a + 0.4) * sstep(3.1, 2.55, z) if flare else 0))  # big soft folds near the flare
        pts.append(Vector((cx + hh * math.copysign(abs(c) ** (2 / e), c),
                           (hh - 0.02) * math.copysign(abs(s) ** (2 / e), s), z)))
    return pts

sleeves = []
for cx in (ARM_CX, -ARM_CX):
    rows = [sleeve_ring(cx, z, SW(z)) for z in [2.46 + (4.0 - 2.46) * k / 12 for k in range(13)]]
    R = 0.1                                               # square Roblox shoulder with a softened edge
    for k in range(1, 5):
        a = (math.pi / 2) * k / 4
        rows.append(sleeve_ring(cx, 4.0 + R * math.sin(a), SW(4.0) - R * (1 - math.cos(a)), flare=False))
    bm = grid_bm(rows, wrap=True, cap_end=True)
    fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
    ob = bm_to_obj(bm, "Sleeve", GREEN); solidify(ob, 0.03); skin(ob, w_arm, bind=False); sleeves.append(ob)
    # strong cuff band + gold stripe
    for (z0, z1, dh, m, th) in ((2.44, 2.6, 0.03, GREEN_TRIM, 0.03), (2.66, 2.705, 0.018, GOLD, 0.012)):
        rows = [sleeve_ring(cx, z, SW(z) + dh + 0.006 * math.sin(math.pi * k / 3), flare=False)
                for k, z in enumerate([z0 + (z1 - z0) * k / 3 for k in range(4)])]
        bm = grid_bm(rows, wrap=True)
        fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
        ob = bm_to_obj(bm, "Cuff", m); solidify(ob, th); skin(ob, w_arm, bind=False); sleeves.append(ob)

# rolled hem: a thicker turned-back edge along the bottom of every panel (hem thickness reads from below)
hem_bm = bmesh.new()
for (ta, tb, ncol) in panels:
    off = coat_off(HEM)
    d = 90 - t_for_x(HEM, XE(HEM), "coat", off)
    a = (90 - d) if ta is None else ta - 2.6
    b = (-270 + d) if tb is None else tb + 2.6
    pts = []
    for j in range(ncol * 2):
        t = a + (b - a) * j / (ncol * 2 - 1)
        p = surf(t, HEM + 0.018, "coat", off - 0.004)
        p += Vector((p.x, p.y - TY(HEM), 0)).normalized() * 0.022 * math.sin(math.radians(t) * 9 + 0.6) * sstep(2.3, 1.3, HEM)
        pts.append(p)
    tube_bm(pts, lambda s: 0.02, 8, bm=hem_bm)
fix_normals(hem_bm)
hem = bm_to_obj(hem_bm, "Coat_Hem", GREEN_SEAM)
skin(hem, w_skirt, bind=False)
coat = join([coat_body, coat_trim, hem] + sleeves, "Coat")
sharpen(coat, 50)
soften(coat, 0.005)

bind_to_rig(coat)

# ---------------------------------------------------------------------------
# 8. wide-leg charcoal trousers, wrapped ankle guards, boots, hand/forearm wraps
# ---------------------------------------------------------------------------
parts = []
rows = [ring(z, "skin", 0.03, 40) for z in [1.85 + (2.56 - 1.85) * k / 6 for k in range(7)]]
bm = grid_bm(rows, wrap=True); fix_normals(bm, axis_center)
ob = bm_to_obj(bm, "Pants_Hip", PANTS); solidify(ob, 0.025); skin(ob, lambda p: w_skirt(p, 0.8), bind=False); parts.append(ob)
PW = Curve1D([(0.62, .52), (0.72, .56), (0.95, .585), (1.4, .575), (2.1, .56)])
for cx in (LEG_CX, -LEG_CX):
    def leg_ring(z, h, n=28):
        pts = []
        for j in range(n):
            a = 2 * math.pi * j / n
            c, s = math.cos(a), math.sin(a)
            fold = 0.01 * math.sin(6 * a + cx * 3) * sstep(1.7, 0.9, z)   # soft vertical folds
            hh = h + fold
            pts.append(Vector((cx + hh * math.copysign(abs(c) ** (2 / 5.0), c),
                               0.0 + (hh - 0.02) * math.copysign(abs(s) ** (2 / 5.0), s), z)))
        return pts
    rows = [leg_ring(z, PW(z)) for z in [0.62 + (2.1 - 0.62) * k / 12 for k in range(13)]]
    bm = grid_bm(rows, wrap=True); fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
    ob = bm_to_obj(bm, "Pants_Leg", PANTS); solidify(ob, 0.028); skin(ob, w_leg, bind=False); parts.append(ob)
pants = join(parts, "Trousers")
soften(pants, 0.004)
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
        bm = grid_bm(band_rings(cx, 0.0, z0, z0 + 0.1, 0.52 + 0.006 * k, 0.014 * (1 if k % 2 else -1),
                                cx * 2, bulge=0.01, e=6.0), wrap=True)          # chunky Roblox leg wraps
        fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
        ob = bm_to_obj(bm, "AnkleWrap", WRAP); solidify(ob, 0.02); parts.append(ob)
wraps_leg = join(parts, "AnkleGuards")
soften(wraps_leg, 0.003)
sharpen(wraps_leg)
skin(wraps_leg, w_leg)

parts = []
for cx in (ARM_CX, -ARM_CX):
    for k, (z0, z1, h) in enumerate([(2.1, 2.22, 0.51), (2.22, 2.34, 0.515), (2.34, 2.48, 0.505)]):
        bm = grid_bm(band_rings(cx, 0.0, z0, z1, h, 0.008 * (1 if k % 2 else -1), 1.0, e=10.0, bulge=0.01), wrap=True)
        fix_normals(bm, lambda c, cx=cx: Vector((cx, 0, c.z)))
        ob = bm_to_obj(bm, "HandWrap", WRAP); solidify(ob, 0.018); parts.append(ob)
wraps_arm = join(parts, "HandWraps")
soften(wraps_arm, 0.003)
sharpen(wraps_arm)
skin(wraps_arm, lambda p: {side(p.x) + ("Hand" if p.z < 2.295 else "LowerArm"): 1.0})

parts = []
for cx in (LEG_CX, -LEG_CX):
    for (cy, cz, sx, sy, sz, bev, m) in [(-0.05, 0.19, 0.53, 0.58, 0.17, 0.08, BOOT),
                                          (-0.055, 0.03, 0.55, 0.6, 0.035, 0.025, SOLE)]:
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
    bm = grid_bm(band_rings(cx, -0.06, 0.2, 0.27, 0.555, 0.04, -math.pi / 2, e=6.0), wrap=True)
    fix_normals(bm, lambda c, cx=cx: Vector((cx, -0.06, c.z)))
    ob = bm_to_obj(bm, "BootStrap", SOLE); solidify(ob, 0.015); parts.append(ob)
boots = join(parts, "Boots")
sharpen(boots, 40)
skin(boots, lambda p: {side(p.x) + "Foot": 1.0})

# ---------------------------------------------------------------------------
# 9. hair: auburn cap, swept fringe, high coiled bun, long loose side lock, gold ornament
# ---------------------------------------------------------------------------
def phi_max(theta):
    """scalp-coverage hairline (hidden under the locks): forehead, well down the sides, nape."""
    t = math.radians(theta)
    return 100 - 52 * math.cos(t) - 4 * math.cos(2 * t)

# thin base layer: only guarantees no scalp shows between locks -- the silhouette comes from the masses
rows = []
for i in range(15):
    s = i / 14
    rr = []
    for j in range(48):
        th = 360 * j / 48
        rr.append(head_P(th, s * phi_max(th), 0.012 + 0.045 * (1 - s ** 4)))
    rows.append(rr)
bm = grid_bm(rows, wrap=True)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
fix_normals(bm, lambda c: HC)
hs_l = bm.verts.layers.float.new("hs"); lv_l = bm.verts.layers.float.new("lockvar")
for v in bm.verts:
    v[hs_l] = 0.0; v[lv_l] = 0.35
hair_parts = [bm_to_obj(bm, "HairBase", HAIR)]

LOCK_ID = [0]
def lock_bm(ctrl, w0, th0, out_fn, n=14, seg=8, wprof=None, tprof=None, bm=None, curl=0.0, twist=0.0):
    """one sculpted anime lock: lens section with curled edges, tapered tip, buried root.
       Stores per-vertex 'hs' (0 root -> 1 tip) and 'lockvar' (per-lock tone) for the hair shader."""
    pts = resample(catmull(ctrl, 10), n)
    bm = bm or bmesh.new()
    hs_l = bm.verts.layers.float.get("hs") or bm.verts.layers.float.new("hs")
    lv_l = bm.verts.layers.float.get("lockvar") or bm.verts.layers.float.new("lockvar")
    LOCK_ID[0] += 1
    tone = (math.sin(LOCK_ID[0] * 12.9898) * 43758.5453) % 1.0
    rows = []
    for i in range(n - 1):
        s = i / (n - 1)
        p = pts[i]
        T = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        o = out_fn(p); o = (o - T * o.dot(T)).normalized()
        B = T.cross(o).normalized()
        if twist:
            q = Matrix.Rotation(twist * s, 3, T)
            B = q @ B; o = q @ o
        w = w0 * (wprof(s) if wprof else (1 - s ** 2.2) ** 0.75 * (0.9 + 0.22 * math.sin(math.pi * s)))
        th = th0 * (tprof(s) if tprof else (1 - s ** 1.6) ** 0.8) + 0.006
        rr = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            c, sn = math.cos(a), math.sin(a)
            rr.append((p + B * (w * 0.5 * c) + o * (th * 0.5 * sn * (1 + 0.2 * sn) - curl * w * c * c), s))
        rows.append(rr)
    V = []
    for r in rows:
        vr = []
        for q, s in r:
            v = bm.verts.new(q); v[hs_l] = s; v[lv_l] = tone; vr.append(v)
        V.append(vr)
    for i in range(len(V) - 1):
        for k in range(seg):
            bm.faces.new((V[i][k], V[i][(k + 1) % seg], V[i + 1][(k + 1) % seg], V[i + 1][k]))
    tv = bm.verts.new(pts[-1]); tv[hs_l] = 1.0; tv[lv_l] = tone
    for k in range(seg):
        bm.faces.new((V[-1][k], V[-1][(k + 1) % seg], tv))
    rv = bm.verts.new(pts[0]); rv[hs_l] = 0.0; rv[lv_l] = tone
    for k in range(seg):
        bm.faces.new((V[0][(k + 1) % seg], V[0][k], rv))
    return bm

head_out = lambda p: (p - HC)
def on_head(theta, phi, off):
    return head_P(theta, phi, off)
def H(pts):
    return [on_head(a, b, o) if not isinstance(a, Vector) else a for a, b, o in pts]

def back_hit(x, z):
    hit = COAT_BVH.ray_cast(Vector((x, 4.0, z)), Vector((0, -1, 0)))
    return (hit[0], hit[1]) if hit[0] is not None else (Vector((x, 0.55, z)), Vector((0, 1, 0)))

def side_out(p):
    if p.z > 4.12:
        return p - HC
    loc, nr, _, _ = FRONT_BVH.find_nearest(p)
    return nr

PART = 14                                  # part sits a little to the wearer's left of centre
TIE = on_head(180, 62, 0.19)               # half-up tie at the back of the crown
def toward_tie(th, k=1.0):
    return TIE + (on_head(th, 64, 0.2) - TIE) * 0.35 * k

hair_bm = bmesh.new()
mass = lambda s: (0.78 + 0.22 * sstep(0.0, 0.2, s)) * (1 - s ** 3) ** 0.55    # broad body, late taper
# ---- PRIMARY: crown masses flowing from the part, over and around the crown, into the tie
CROWN = [   # offsets stay close to the head at the sides so no ledge forms; volume sits on top / back
    ([(PART + 2, 14, .06), (40, 28, .16), (80, 46, .17), (128, 60, .17)], toward_tie(150), .52, .13),
    ([(PART + 2, 30, .06), (54, 38, .19), (104, 54, .17), (150, 63, .18)], toward_tie(165), .5, .13),
    ([(PART, 6, .06), (44, 12, .17), (118, 36, .21), (168, 56, .2)], toward_tie(175, 0.6), .5, .14),
    ([(PART - 2, 14, .06), (-14, 28, .16), (-58, 46, .17), (-112, 58, .17)], toward_tie(-150), .56, .14),
    ([(PART - 2, 30, .06), (-30, 36, .19), (-86, 50, .17), (-140, 61, .18)], toward_tie(-165), .52, .13),
    ([(PART, 6, .06), (-26, 14, .17), (-116, 36, .21), (-170, 56, .2)], toward_tie(-175, 0.6), .5, .14),
]
for pts, end, w, th in CROWN:
    lock_bm(H(pts) + [end], w, th, head_out, n=14, bm=hair_bm, curl=0.09, wprof=mass,
            tprof=lambda s: (0.7 + 0.3 * math.sin(math.pi * min(1, s * 1.3))))
# upper back: sweeps up from behind the ears into the tie
for th in (116, 136, 160, 200, 224, 244):
    ctrl = [on_head(th, 108, .04), on_head(th + (180 - th) * 0.15, 92, .12),
            on_head(th + (180 - th) * 0.45, 74, .16), toward_tie(180 + (th - 180) * 0.3, 0.5)]
    lock_bm(ctrl, 0.42, 0.1, head_out, n=12, bm=hair_bm, curl=0.08, wprof=mass)

# ---- SECONDARY: layered bangs from the part, different lengths and directions, overlapping
BANGS = [   # (ctrl, width, thickness, curl) -- kept close to the forehead: no visor
    ([(PART - 2, 16, .08), (0, 40, .14), (-22, 62, .12), (-44, 78, .08), (-60, 94, .045), (-66, 108, .02)], .44, .1, .07),  # long sweep
    ([(PART, 22, .08), (10, 44, .13), (3, 64, .1), (-4, 78, .05), (-8, 86, .02)], .3, .085, .06),                         # centre
    ([(PART + 4, 18, .08), (30, 38, .13), (42, 58, .1), (51, 72, .05), (55, 80, .02)], .32, .085, .06),                   # short left
    ([(4, 32, .1), (-10, 52, .11), (-18, 70, .06), (-21, 81, .02)], .22, .065, .05),                                       # accent
]
for ctrl, w, th, cu in BANGS:
    lock_bm(H(ctrl), w, th, head_out, n=14, bm=hair_bm, curl=cu)

# ---- SECONDARY: side volume over the temples / cheeks (asymmetric: right side longer)
SIDES = [
    ([(66, 30, .1), (82, 62, .16), (91, 98, .16), (94, 124, .1)], Vector((0.55, -0.12, 4.18)), .42, .13),
    ([(100, 34, .09), (108, 72, .16), (112, 106, .15)], Vector((0.6, 0.1, 4.15)), .42, .13),
    ([(-64, 28, .1), (-80, 62, .17), (-90, 98, .17), (-93, 124, .11)], Vector((-0.57, -0.12, 4.12)), .44, .14),
    ([(-98, 34, .09), (-108, 72, .16), (-113, 106, .16)], Vector((-0.63, 0.12, 4.12)), .44, .13),
]
for ctrl, end, w, th in SIDES:
    lock_bm(H(ctrl) + [end], w, th, head_out, n=13, bm=hair_bm, curl=0.06,
            wprof=lambda s: (0.8 + 0.2 * sstep(0, 0.2, s)) * (1 - s ** 2.4) ** 0.7)

# ---- ACCENT: two long face-framing locks resting on the robe front (right one longer)
for sg, hits, w in ((-1, [(-0.55, 3.98, .13), (-0.62, 3.72, .1), (-0.58, 3.46, .08), (-0.64, 3.2, .06)], .27),
                    (1, [(0.55, 3.98, .13), (0.6, 3.74, .1), (0.62, 3.54, .07)], .24)):
    top = [on_head(sg * 58, 34, .1), on_head(sg * 72, 68, .15), on_head(sg * 79, 98, .13),
           HC + head_dir(sg * 82, 122) * 0.74]
    low = []
    for x, z, lift in hits:
        loc, nr = front_hit(FRONT_BVH, x, z)
        low.append(loc + nr * lift)
    lock_bm(top + low, w, 0.1, side_out, n=18, bm=hair_bm, curl=0.06,
            wprof=lambda s: (1 - s ** 2.2) ** 0.8 * (0.85 + 0.25 * math.sin(math.pi * s)))

# ---- PRIMARY: loose lower back -- broad, overlapping, varied lengths, directional (no saw blade)
BACK = [(128, 3.72, 0.02), (148, 3.5, -0.03), (166, 3.36, 0.02), (184, 3.28, 0.04), (202, 3.42, -0.02),
        (220, 3.58, 0.03), (238, 3.78, -0.02)]
for th, end, dx in BACK:
    x0 = 0.58 * math.sin(math.radians(th))
    ctrl = [on_head(th, 104, .09), on_head(th, 124, .16), on_head(th, 140, .17)]
    for x, z, lift in [(x0 * 1.02, 3.98, 0.15), (x0 * 1.06 + dx, 3.74, 0.14), (x0 * 1.02 + dx * 2, (3.74 + end) / 2, 0.12),
                       (x0 * 0.95 + dx * 3, end, 0.1)]:
        loc, nr = back_hit(x, z)
        ctrl.append(loc + nr * lift)
    lock_bm(ctrl, 0.44, 0.1, lambda p: (p - HC) if p.z > 4.15 else Vector((0, 1, 0)), n=20, bm=hair_bm, curl=0.07,
            wprof=lambda s: (0.85 + 0.15 * sstep(0, 0.2, s)) * (1 - s ** 3.2) ** 0.55)
fix_normals(hair_bm)
hair_parts.append(bm_to_obj(hair_bm, "HairLocks", HAIR))

# ---- PONYTAIL: four locks gathered at the tie, each curving on its own
tail_bm = bmesh.new()
tail_out = lambda p: Vector((0, 1, 0.3))
tail_w = lambda s: (0.9 + 0.1 * sstep(0.0, 0.15, s)) * (1 - s ** 2.4) ** 0.7 * (1 + 0.25 * math.sin(math.pi * s))
MAIN = [TIE + Vector((0, -0.06, 0)), TIE + Vector((0, 0.24, 0.08)), TIE + Vector((0.02, 0.44, -0.12)),
        TIE + Vector((0.06, 0.44, -0.5)), TIE + Vector((0.03, 0.34, -0.9)), TIE + Vector((0.1, 0.24, -1.26))]
lock_bm(MAIN, 0.4, 0.28, tail_out, n=16, bm=tail_bm, curl=0.04, wprof=tail_w)
TAILS = [
    ([Vector((0.06, -0.03, 0.02)), Vector((0.18, 0.22, 0.04)), Vector((0.3, 0.38, -0.2)), Vector((0.36, 0.38, -0.55)),
      Vector((0.3, 0.3, -0.86))], .3, .2),
    ([Vector((-0.06, -0.03, 0.02)), Vector((-0.16, 0.24, 0.06)), Vector((-0.27, 0.4, -0.14)), Vector((-0.3, 0.42, -0.44)),
      Vector((-0.4, 0.34, -0.7))], .28, .18),
    ([Vector((0, -0.02, 0.06)), Vector((0.02, 0.28, 0.2)), Vector((0.05, 0.5, 0.14)), Vector((0.1, 0.62, -0.05))], .24, .14),
]
for ctrl, w, th in TAILS:
    lock_bm([TIE + c for c in ctrl], w, th, tail_out, n=13, bm=tail_bm, curl=0.05, wprof=tail_w)
fix_normals(tail_bm)
hair_parts.append(bm_to_obj(tail_bm, "HairPonytail", HAIR))
hair = join(hair_parts, "Hair")
sharpen(hair, 55)                                          # clean modelled lock edges, smooth broad faces
skin(hair, lambda p: {"Head": 1.0} if p.z > 4.2
     else {"Head": 0.35 + 0.65 * sstep(3.4, 4.2, p.z), "UpperTorso": 0.65 * (1 - sstep(3.4, 4.2, p.z))})

# --- gold ornament at the tie: wrapped band + hairpin with jade flower and dangling beads
parts = []
tdir = (MAIN[1] - MAIN[0]).normalized()
rot = tdir.to_track_quat("Z", "Y").to_matrix()
bm = bmesh.new()
for k, (dz, r) in enumerate(((0.0, 0.17), (0.05, 0.165))):
    c = TIE + tdir * (0.06 + dz)
    tube_bm([c + rot @ Vector((r * math.cos(2 * math.pi * i / 36), r * 0.8 * math.sin(2 * math.pi * i / 36), 0)) for i in range(37)],
            lambda s: 0.022, 8, bm=bm, cap=False)
fix_normals(bm); parts.append(bm_to_obj(bm, "OrnBand", GOLD))
pin_a = TIE + Vector((0.36, 0.1, 0.1))
pin_b = TIE + Vector((-0.3, 0.14, -0.06))
bm = tube_bm([pin_a.lerp(pin_b, k / 10) for k in range(11)], lambda s: 0.017 * (1 - 0.6 * s), 8)
fix_normals(bm); parts.append(bm_to_obj(bm, "OrnPin", GOLD))
fl_n = (pin_a - pin_b).normalized()
fl_c = pin_a + fl_n * 0.02
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
# 10. material depth: per-vertex wear/edge attributes + differentiated procedural materials
#     (render look for review; the attributes stay on the meshes for later texture baking)
# ---------------------------------------------------------------------------
def write_attr(ob, name, fn_or_list):
    me = ob.data
    at = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    vals = fn_or_list if isinstance(fn_or_list, list) else [fn_or_list(v.co) for v in me.vertices]
    at.data.foreach_set("value", [max(0.0, min(1.0, x)) for x in vals])

def edge_mask(ob, angle=55, grow=1):
    """1.0 on hard rims (hems, cuffs, garment edges) -> worn / faded edges."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    lim = math.radians(angle)
    val = [0.0] * len(bm.verts)
    for e in bm.edges:
        if e.is_boundary or (e.is_manifold and e.calc_face_angle(0) > lim):
            for v in e.verts:
                val[v.index] = 1.0
    for _ in range(grow):
        nv = val[:]
        for v in bm.verts:
            if val[v.index] < 1:
                m = max((val[o.index] for e in v.link_edges for o in e.verts), default=0)
                nv[v.index] = max(val[v.index], m * 0.5)
        val = nv
    bm.free()
    return val

def is_sleeve(p):
    return abs(p.x) > 1.02 and 2.4 < p.z < 4.12
ob = bpy.data.objects["Coat"]
write_attr(ob, "wear", lambda p: max(0.9 * sstep(HEM + 0.32, HEM, p.z),
                                     0.85 * sstep(2.95, 2.56, p.z) if is_sleeve(p) else 0.0,
                                     0.35 * sstep(3.4, 3.1, p.z) * sstep(0.95, 1.1, abs(p.x)) if not is_sleeve(p) else 0.0))
write_attr(ob, "edge", edge_mask(ob))
ob = bpy.data.objects["InnerTop"]
write_attr(ob, "wear", lambda p: 0.6 * sstep(2.78, 2.5, p.z))
write_attr(ob, "edge", edge_mask(ob))
for n in ("InnerTop_Collar", "Sash", "Boots"):
    write_attr(bpy.data.objects[n], "edge", edge_mask(bpy.data.objects[n]))
write_attr(bpy.data.objects["Sash"], "wear", lambda p: 0.5 * sstep(0.02, 0.0, abs(p.z - 2.67)) + 0.3)
ob = bpy.data.objects["Trousers"]
write_attr(ob, "wear", lambda p: max(0.8 * sstep(0.95, 0.66, p.z), 0.35 * sstep(0.2, 0.0, abs(p.z - 1.2)) * (p.y < 0)))
write_attr(ob, "edge", edge_mask(ob))
ob = bpy.data.objects["AnkleGuards"]
write_attr(ob, "wear", lambda p: 0.9 * sstep(0.5, 0.28, p.z)); write_attr(ob, "edge", edge_mask(ob))
ob = bpy.data.objects["HandWraps"]
write_attr(ob, "wear", lambda p: 0.8 * sstep(2.28, 2.03, p.z)); write_attr(ob, "edge", edge_mask(ob))
write_attr(bpy.data.objects["Boots"], "wear", lambda p: 0.8 * sstep(0.12, 0.0, p.z) + 0.4 * (p.y < -0.35))

def N(nt, kind, loc=(0, 0), **inputs):
    n = nt.nodes.new(kind); n.location = loc
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n

def mixc(nt, fac_socket, a, b):
    m = nt.nodes.new("ShaderNodeMix"); m.data_type = "RGBA"; m.blend_type = "MIX"
    if isinstance(fac_socket, float):
        m.inputs[0].default_value = fac_socket
    else:
        nt.links.new(fac_socket, m.inputs[0])
    for sock, val in ((6, a), (7, b)):
        if isinstance(val, (tuple, list)):
            m.inputs[sock].default_value = val
        else:
            nt.links.new(val, m.inputs[sock])
    return m.outputs[2]

def maprange(nt, sock, a, b, c, d):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value = a; m.inputs["From Max"].default_value = b
    m.inputs["To Min"].default_value = c; m.inputs["To Max"].default_value = d
    nt.links.new(sock, m.inputs["Value"])
    return m.outputs["Result"]

def mathop(nt, op, a, b):
    m = nt.nodes.new("ShaderNodeMath"); m.operation = op
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]

def scale_rgb(c, k, sat=1.0):
    g = (c[0] + c[1] + c[2]) / 3
    return tuple(max(0.0, min(1.0, (g + (x - g) * sat) * k)) for x in c[:3]) + (1.0,)

def surface_shader(m, *, weave=0.0, weave_str=0.0, bands=0.0, var=0.08, rough=(0.7, 0.9), fold=0.12,
                   grime=None, grime_amt=0.0, fade=None, fade_amt=0.0, ao=0.45, grain=0.0):
    """stylised material: colour breakup, weave / grain bump, large soft fold shading, AO in overlaps,
       wear (grime at cuffs/hems) and faded edges. All procedural, object-space."""
    nt = m.node_tree; L = nt.links
    b = nt.nodes["Principled BSDF"]
    if b.inputs["Base Color"].is_linked:
        col = b.inputs["Base Color"].links[0].from_socket
        base = None
    else:
        base = tuple(b.inputs["Base Color"].default_value)
        col = None
    tc = N(nt, "ShaderNodeTexCoord")
    nz = N(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=4.0, Roughness=0.55)
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    fine = N(nt, "ShaderNodeTexNoise", Scale=38.0, Detail=2.0)
    L.new(tc.outputs["Object"], fine.inputs["Vector"])
    # colour breakup
    vfac = maprange(nt, nz.outputs["Fac"], 0.3, 0.7, 0.0, 1.0)
    if base is not None:
        c = mixc(nt, vfac, scale_rgb(base, 1.0 + var, 1.05), scale_rgb(base, 1.0 - var, 0.92))
    else:
        c = mixc(nt, vfac, col, col)
    # grime (darker, slightly desaturated) at cuffs / hems / contact areas
    if grime_amt:
        wa = N(nt, "ShaderNodeAttribute"); wa.attribute_name = "wear"
        g = mathop(nt, "MULTIPLY", wa.outputs["Fac"], maprange(nt, fine.outputs["Fac"], 0.25, 0.75, 0.55, 1.0))
        g = mathop(nt, "MULTIPLY", g, grime_amt)
        c = mixc(nt, g, c, grime if grime else scale_rgb(base, 0.62, 0.8))
    # faded / rubbed edges
    if fade_amt:
        ea = N(nt, "ShaderNodeAttribute"); ea.attribute_name = "edge"
        f = mathop(nt, "MULTIPLY", ea.outputs["Fac"], maprange(nt, fine.outputs["Fac"], 0.3, 0.7, 0.3, 1.0))
        f = mathop(nt, "MULTIPLY", f, fade_amt)
        c = mixc(nt, f, c, fade if fade else scale_rgb(base, 1.35, 0.7))
    # ambient occlusion: fabric overlaps, folds, under-bust, lapels
    if ao:
        aon = N(nt, "ShaderNodeAmbientOcclusion", Distance=0.12)
        L.new(c, aon.inputs["Color"])
        c = mixc(nt, float(ao), c, aon.outputs["Color"])
    L.new(c, b.inputs["Base Color"])
    # roughness variation
    L.new(maprange(nt, nz.outputs["Fac"], 0.3, 0.7, rough[0], rough[1]), b.inputs["Roughness"])
    # bump: weave (two crossing band sets), horizontal compression bands, grain, large folds
    h = None
    if weave:
        wx = N(nt, "ShaderNodeTexWave", Scale=weave, Distortion=0.0); wx.bands_direction = "X"
        wy = N(nt, "ShaderNodeTexWave", Scale=weave, Distortion=0.0); wy.bands_direction = "Y"
        for w in (wx, wy):
            L.new(tc.outputs["Object"], w.inputs["Vector"])
        h = mathop(nt, "MULTIPLY", wx.outputs["Fac"], wy.outputs["Fac"])
    if bands:
        wz = N(nt, "ShaderNodeTexWave", Scale=bands, Distortion=1.5); wz.bands_direction = "Z"
        L.new(tc.outputs["Object"], wz.inputs["Vector"])
        h = wz.outputs["Fac"] if h is None else mathop(nt, "ADD", h, wz.outputs["Fac"])
    normal = None
    if h is not None and weave_str:
        bp = N(nt, "ShaderNodeBump", Strength=weave_str, Distance=0.002)
        L.new(h, bp.inputs["Height"]); normal = bp.outputs["Normal"]
    if grain:
        bp = N(nt, "ShaderNodeBump", Strength=grain, Distance=0.002)
        L.new(fine.outputs["Fac"], bp.inputs["Height"])
        if normal is not None:
            L.new(normal, bp.inputs["Normal"])
        normal = bp.outputs["Normal"]
    if fold:
        big = N(nt, "ShaderNodeTexNoise", Scale=2.2, Detail=1.0)
        L.new(tc.outputs["Object"], big.inputs["Vector"])
        bp = N(nt, "ShaderNodeBump", Strength=fold, Distance=0.05)
        L.new(big.outputs["Fac"], bp.inputs["Height"])
        if normal is not None:
            L.new(normal, bp.inputs["Normal"])
        normal = bp.outputs["Normal"]
    if normal is not None:
        L.new(normal, b.inputs["Normal"])

def set_bsdf(m, **kw):
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        b.inputs[k].default_value = v

# matte robe: weave, soft folds, darker grime at cuffs/hem, rubbed edges
surface_shader(GREEN, weave=210, weave_str=0.07, var=0.1, rough=(0.8, 0.95), fold=0.18,
               grime_amt=0.55, fade=scale_rgb(GREEN.diffuse_color, 1.45, 0.75), fade_amt=0.5, ao=0.5)
set_bsdf(GREEN, **{"Sheen Weight": 0.45, "Specular IOR Level": 0.25})
surface_shader(GREEN_TRIM, weave=240, weave_str=0.06, var=0.08, rough=(0.72, 0.88), fold=0.08,
               fade=scale_rgb(GREEN_TRIM.diffuse_color, 1.7, 0.8), fade_amt=0.55, ao=0.45)
surface_shader(GREEN_SEAM, weave=0, var=0.06, rough=(0.75, 0.9), fold=0.0, ao=0.5)
# soft cloth inner garment: fine weave, gentle folds, warm off-white, shadow where it overlaps
surface_shader(CREAM, weave=260, weave_str=0.05, var=0.05, rough=(0.85, 0.97), fold=0.2,
               grime=srgb(208, 192, 166), grime_amt=0.5, fade_amt=0.0, ao=0.6)
set_bsdf(CREAM, **{"Sheen Weight": 0.35, "Specular IOR Level": 0.2})
surface_shader(CREAM_TRIM, weave=260, weave_str=0.05, var=0.05, rough=(0.8, 0.95), fold=0.06,
               fade_amt=0.4, ao=0.5)
# heavier woven sash: coarse weave + horizontal compression lines
surface_shader(SASH, weave=120, weave_str=0.14, bands=26, var=0.12, rough=(0.62, 0.85), fold=0.1,
               grime=srgb(12, 16, 30), grime_amt=0.5, fade=srgb(60, 70, 104), fade_amt=0.45, ao=0.6)
surface_shader(SASH2, weave=120, weave_str=0.14, bands=26, var=0.12, rough=(0.62, 0.85), fold=0.1,
               fade=srgb(96, 106, 140), fade_amt=0.4, ao=0.6)
surface_shader(PANTS, weave=200, weave_str=0.06, var=0.08, rough=(0.8, 0.95), fold=0.2,
               grime=srgb(58, 52, 46), grime_amt=0.45, fade_amt=0.25, ao=0.5)
surface_shader(WRAP, weave=90, weave_str=0.12, bands=40, var=0.07, rough=(0.85, 0.98), fold=0.05,
               grime=srgb(176, 160, 136), grime_amt=0.6, fade_amt=0.0, ao=0.6)
# leather: grain + roughness variation + lighter scuffs on toes / edges
surface_shader(BOOT, grain=0.035, var=0.07, rough=(0.38, 0.62), fold=0.05,
               grime=srgb(26, 18, 16), grime_amt=0.5, fade=srgb(92, 68, 54), fade_amt=0.6, ao=0.4)
surface_shader(SOLE, grain=0.08, var=0.08, rough=(0.65, 0.85), fold=0.0, ao=0.4)
surface_shader(LEATHER, grain=0.04, var=0.08, rough=(0.4, 0.62), fold=0.0, fade_amt=0.0, ao=0.4)
surface_shader(CORD, weave=0, bands=90, weave_str=0.2, var=0.06, rough=(0.35, 0.55), fold=0.0, ao=0.3)
# metal: real metallic response with slight roughness breakup
surface_shader(GOLD, grain=0.04, var=0.06, rough=(0.18, 0.34), fold=0.0, ao=0.2)
# skin: smooth, not plastic -- a touch of subsurface, low specular
set_bsdf(SKIN, **{"Roughness": 0.5, "Specular IOR Level": 0.28, "Subsurface Weight": 0.12,
                  "Subsurface Radius": (0.08, 0.03, 0.02), "Subsurface Scale": 0.05, "Coat Weight": 0.0})
# hair: restrained stylised shader -- darker roots / recesses, lighter broad tips, per-lock tone, soft sheen
nt = HAIR.node_tree
for n in list(nt.nodes):
    if n.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL"):
        nt.nodes.remove(n)
bsdf = nt.nodes["Principled BSDF"]
hs = N(nt, "ShaderNodeAttribute"); hs.attribute_name = "hs"
lv = N(nt, "ShaderNodeAttribute"); lv.attribute_name = "lockvar"
geo = N(nt, "ShaderNodeNewGeometry"); sep = N(nt, "ShaderNodeSeparateXYZ")
nt.links.new(geo.outputs["Position"], sep.inputs[0])
zf = maprange(nt, sep.outputs["Z"], 3.3, 5.3, 0.0, 1.0)
f = mathop(nt, "MULTIPLY", hs.outputs["Fac"], 0.42)
f = mathop(nt, "ADD", f, maprange(nt, lv.outputs["Fac"], 0.0, 1.0, -0.12, 0.12))
f = mathop(nt, "ADD", f, mathop(nt, "MULTIPLY", zf, 0.28))
f = mathop(nt, "ADD", f, 0.14)
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.1; ramp.color_ramp.elements[0].color = srgb(62, 14, 10)
ramp.color_ramp.elements[1].position = 0.95; ramp.color_ramp.elements[1].color = srgb(184, 64, 38)
mid = ramp.color_ramp.elements.new(0.5); mid.color = srgb(126, 34, 22)
nt.links.new(f, ramp.inputs["Fac"])
aon = N(nt, "ShaderNodeAmbientOcclusion", Distance=0.12)
nt.links.new(ramp.outputs["Color"], aon.inputs["Color"])
nt.links.new(mixc(nt, 0.6, ramp.outputs["Color"], aon.outputs["Color"]), bsdf.inputs["Base Color"])
set_bsdf(HAIR, **{"Roughness": 0.4, "Anisotropic": 0.55, "Specular IOR Level": 0.42, "Coat Weight": 0.06,
                  "Coat Roughness": 0.35, "Sheen Weight": 0.15})

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
ARM["hb_template"] = "HealerBrawler v7 -- v6 + ellipsoid bust volumes and clothing fit"
print("TRIS", tris, "TOTAL", sum(tris.values()))

txt = bpy.data.texts.new("build_healer_brawler_v7.py")
txt.from_string(open(os.path.abspath(__file__)).read())

# neutral stage for opening the file
sc = bpy.context.scene
sc.render.engine = "CYCLES"
bpy.ops.wm.save_as_mainfile(filepath=OUT_PATH, compress=True)
print("SAVED", OUT_PATH)
