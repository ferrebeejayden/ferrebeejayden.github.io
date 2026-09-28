"""
Review renders for the Healer/Brawler unit (denoised Cycles).

    python3 render_reviews.py <model.blend> <out_dir> [shot ...]

Poses are applied in FK on the R15 bones (the way Roblox Motor6D animations drive
them): the IK / Child-Of helper constraints and the rest action are muted in this
render session only -- the saved model file is never modified.
"""
import bpy, math, sys, os
from mathutils import Vector, Matrix, Quaternion

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
MODEL, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
ONLY = set(argv[2:])
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=MODEL)
sc = bpy.context.scene
ARM = bpy.data.objects["__Rig"]
ARM.hide_render = True

# ---------------------------------------------------------------- render setup
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = int(os.environ.get("HB_SAMPLES", 64))
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6
sc.render.film_transparent = False
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.image_settings.file_format = "PNG"

world = bpy.data.worlds.new("HB_World")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.055, 0.058, 0.065, 1)
bg.inputs["Strength"].default_value = 0.6
sc.world = world

def light(name, kind, loc, energy, size, color=(1, 1, 1), target=(0, 0, 2.6)):
    L = bpy.data.lights.new(name, kind)
    L.energy = energy; L.color = color
    if kind == "AREA":
        L.size = size
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o

light("Key", "AREA", (-5.5, -7.5, 7.5), 2600, 5, (1.0, 0.96, 0.9))
light("Fill", "AREA", (7.5, -5.0, 4.0), 900, 6, (0.88, 0.93, 1.0))
light("Rim", "AREA", (3.0, 8.0, 7.0), 2200, 4, (0.95, 0.97, 1.0))
light("RimL", "AREA", (-6.0, 6.0, 5.0), 900, 4)

floor_me = bpy.data.meshes.new("floor")
floor_me.from_pydata([(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], [], [(0, 1, 2, 3)])
floor = bpy.data.objects.new("Floor", floor_me); sc.collection.objects.link(floor)
fm = bpy.data.materials.new("Floor"); fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.07, 0.072, 0.08, 1)
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
floor_me.materials.append(fm)

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data); sc.collection.objects.link(cam)
sc.camera = cam

def aim(loc, target, lens=60, ortho=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_data.type = "ORTHO"; cam_data.ortho_scale = ortho
    else:
        cam_data.type = "PERSP"; cam_data.lens = lens

# ---------------------------------------------------------------- FK posing
if ARM.animation_data:
    ARM.animation_data.action = None
for pb in ARM.pose.bones:
    for c in pb.constraints:
        c.mute = True
    pb.rotation_mode = "QUATERNION"

def reset_pose():
    for pb in ARM.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()

def rotate_world(bone, axis, deg, pivot=None):
    """rotate a pose bone (and its children) about a world axis through its head."""
    pb = ARM.pose.bones[bone]
    bpy.context.view_layer.update()
    M = pb.matrix.copy()
    piv = Vector(pivot) if pivot else M.to_translation()
    R = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-piv)
    pb.matrix = R @ M
    bpy.context.view_layer.update()

def arms(deg_left, deg_right, fwd=0.0):
    # abduction: left arm swings toward +X, right toward -X
    rotate_world("LeftUpperArm", "Y", -deg_left)
    rotate_world("RightUpperArm", "Y", deg_right)

POSES = {
    "neutral": lambda: None,
    "arms45": lambda: arms(45, 45),
    "arms90": lambda: arms(90, 90),
    "armraise": lambda: (arms(20, 155), rotate_world("LeftLowerArm", "X", -25)),
    "twist": lambda: (rotate_world("UpperTorso", "Z", 22), arms(30, 30), rotate_world("Head", "Z", -10)),
}

# ---------------------------------------------------------------- shots
FULL_T = (0, 0, 2.62)
SHOTS = {
    "01_front34": dict(pose="neutral", cam=((-5.6, -9.4, 3.9), FULL_T, 58), res=(1100, 1400)),
    "02_front": dict(pose="neutral", cam=((0, -11.5, 2.8), FULL_T, 58), res=(1100, 1400)),
    "03_side": dict(pose="neutral", cam=((-11.5, -0.05, 2.8), FULL_T, 58), res=(1100, 1400)),
    "04_back": dict(pose="neutral", cam=((3.2, 11.0, 3.4), FULL_T, 58), res=(1100, 1400)),
    "05_torso_close": dict(pose="neutral", cam=((-2.0, -4.6, 3.75), (0, -0.3, 3.2), 60), res=(1200, 1200)),
    "05b_torso_side": dict(pose="neutral", cam=((-4.6, -1.6, 3.6), (0, -0.35, 3.15), 60), res=(1200, 1200)),
    "06_hair_close": dict(pose="neutral", cam=((2.6, 2.8, 5.4), (0, 0.05, 4.7), 60), res=(1200, 1200)),
    "06b_face_close": dict(pose="neutral", cam=((-1.1, -3.4, 4.75), (0, -0.2, 4.6), 70), res=(1200, 1200)),
    "07_silhouette_front": dict(pose="neutral", cam=((0, -11.5, 2.8), FULL_T, 58), res=(900, 1150), sil=True),
    "07b_silhouette_side": dict(pose="neutral", cam=((-11.5, -0.05, 2.8), FULL_T, 58), res=(900, 1150), sil=True),
    "07c_silhouette_34": dict(pose="neutral", cam=((-5.6, -9.4, 3.9), FULL_T, 58), res=(900, 1150), sil=True),
    "08_arms45": dict(pose="arms45", cam=((-3.5, -10.5, 3.6), FULL_T, 52), res=(1300, 1300)),
    "09_arms90": dict(pose="arms90", cam=((-3.5, -10.5, 3.6), FULL_T, 48), res=(1400, 1200)),
    "09b_arms90_back": dict(pose="arms90", cam=((3.0, 10.5, 4.2), (0, 0, 3.0), 48), res=(1400, 1200)),
    "10_armraise": dict(pose="armraise", cam=((-4.5, -9.5, 3.6), (0, 0, 3.0), 50), res=(1200, 1400)),
    "11_torso_twist": dict(pose="twist", cam=((-3.0, -10.5, 3.6), FULL_T, 52), res=(1200, 1300)),
}

sil_mat = bpy.data.materials.new("Sil"); sil_mat.use_nodes = True
nt = sil_mat.node_tree; nt.nodes.clear()
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.02, 0.02, 0.025, 1)
out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs[0], out.inputs[0])

for name, s in SHOTS.items():
    if ONLY and name not in ONLY:
        continue
    reset_pose()
    POSES[s["pose"]]()
    loc, tgt, lens = s["cam"]
    aim(loc, tgt, lens)
    sc.render.resolution_x, sc.render.resolution_y = s["res"]
    sil = s.get("sil", False)
    sc.view_layers[0].material_override = sil_mat if sil else None
    floor.hide_render = sil
    bg.inputs["Color"].default_value = (1, 1, 1, 1) if sil else (0.055, 0.058, 0.065, 1)
    bg.inputs["Strength"].default_value = 1.0 if sil else 0.6
    sc.view_settings.view_transform = "Standard" if sil else "AgX"
    if not sil:
        sc.view_settings.look = "AgX - Medium High Contrast"
    sc.cycles.samples = 8 if sil else int(os.environ.get("HB_SAMPLES", 64))
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)
