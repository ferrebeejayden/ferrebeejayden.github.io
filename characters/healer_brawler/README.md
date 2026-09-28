# Healer / Brawler unit: R15 character template

An original adult anime-style healer/brawler built on the supplied blank Roblox R15 rig
(`BauzlyIKRig.blend`). It's meant as a reusable modeling template: every part comes from
shared parametric functions and is skinned to the untouched `__Rig` armature.

| File | What it is |
|---|---|
| `HealerBrawler_R15.blend` | The model. It's a new file; the blank rig was only read. |
| `build_healer_brawler.py` | Procedural generator (also embedded in the .blend as a Text block). |
| `render_reviews.py` | Review renders (denoised Cycles) and FK pose tests. |
| `make_sheet.py` | Builds the contact sheet `renders/00_review_sheet.png`. |
| `renders/` | Front 3/4, front, side, back, torso close-ups, hair and face close-ups, silhouettes, arms 45°/90°, one arm raised, torso twist. |

```
python3 build_healer_brawler.py <blank_rig.blend> HealerBrawler_R15.blend
python3 render_reviews.py HealerBrawler_R15.blend renders
python3 make_sheet.py renders renders/00_review_sheet.png
```
You need Blender 4.2 or the `bpy==4.2` module. `render_reviews.py` also needs Pillow for the sheet.

## Rig
- The `__Rig` armature, bone names, hierarchy, scale, constraints and `__RigAction` are unchanged.
- Every new mesh is parented to `__Rig` and has an Armature modifier. Weights use only the 15 R15
  deform bones (`LowerTorso`, `UpperTorso`, `Head`, the arm, hand, leg and foot bones).
- The supplied blank part meshes are kept in `R15_BlankParts_Reference`, hidden. The skinned
  `Body_Limbs` copies them. Limb blocks under clothing are slightly slimmed so their corners never
  poke through.
- Note: in the supplied file, the rig's default *evaluated* pose (the `Bone` controller, Child-Of
  and IK helpers, and the frame-0 action) sits about 2–4 cm off the bind/rest pose. The meshes are
  bound to the true rest pose. The pose tests run in FK from rest, the way Motor6D animations drive
  the bones, with the helper constraints muted only in the render session.

## Template knobs (in `build_healer_brawler.py`)
- `TW / TD / TN / TY`: torso half-width, half-depth, squareness and posture per height.
- `BUST`, `INNER`, `DRAPE`: rounded upper-torso forms. `INNER` sets how deep the central
  separation is for each layer (skin, cloth, coat). `DRAPE` sets how far fabric falls from the underside.
- `surf(t, z, mode, off)`: any garment layer is the body surface pushed out along its normal.
  `underarm()` flattens each layer where the blocky arm hangs.
- `Z_CROSS / GAP`: crossing height and V shape of the wrapped top. `XE`: coat front-edge line.
  `SLIT_TOP`: coat slits (sides and back).
- `FRINGE`, lock lists, `phi_max`: hair layout. Locks are (theta, phi, offset) paths on the head.
- Weight helpers `w_torso`, `w_skirt`, `w_arm`, `w_leg`: reuse them for new garments.

## Budget
About 73k triangles in total. The largest mesh is `Coat` at about 21k. If you need to stay under
Roblox's per-MeshPart limit, split the coat's sleeves off or lower the row/column counts in the builder.
