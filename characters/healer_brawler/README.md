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

---

## v2: art-direction and silhouette pass

`HealerBrawler_R15_v2.blend` is built by `build_healer_brawler_v2.py`. v1 (`HealerBrawler_R15.blend`,
`build_healer_brawler.py`, `renders/`) is left untouched. The rig, weighting helpers, pose tests and
garment structure are the same; the visible geometry was redesigned:

- **Shoulders and sleeves:** the visible arm mass moves inward (`ARM_CX` 1.5 → 1.3) and is slimmed.
  Sleeves are now lantern-shaped cloth with a rounded, sloped shoulder cap and a set-in inner edge.
  They are slightly fuller in the upper sleeve and taper to a thin cuff. Across the sleeves, the
  character is about 20% narrower. Bones are unchanged; only the arm blocks in the skinned
  `Body_Limbs` mesh are slimmed and moved inward.
- **Torso:** hourglass profile (waist half-width 0.755 → 0.60, narrower chest and shoulders). The bust
  uses a soft falloff (`p = 2`) so it blends into the chest wall.
- **Wrapped top:** thinner fabric, a deeper crossing, and slim lapel bands built analytically on the
  garment surface (`front_point` / `param_ribbon`), so they curve cleanly over the bust and cross
  neatly into the sash.
- **Coat:** thinner (offset 0.08, thickness 0.022), tapered at the waist, flared toward a longer hem
  (`HEM` 0.72). Front trim tapers toward the hem; slimmer standing collar.
- **Sash:** narrower (0.30 tall) with three layers: navy main band, slanted slate wrap and a thin
  under-band. Smaller cord, knot and pouch.
- **Lower body:** narrower trousers (`LEG_CX` 0.45), ankle guards that taper toward the ankle, and
  narrower boots.
- **Hair:** fuller crown, a large layered swept fringe, framing locks on both sides, side and back
  masses swept up into a coiled bun with two tufts, subtle nape strands, one long S-curve strand, and
  an auburn gradient shader (for renders only).
- **Face:** almond eyes with a lifted outer corner and a heavier lash wing, lid crease, a lid shadow on
  the iris, slim angular brows (one slightly raised), a smirk and a narrower jaw.
- **Palette:** deeper green robe, darker trim, warmer off-white, deeper navy, richer auburn.

About 68k triangles (v1: 73k).

```
python3 build_healer_brawler_v2.py <blank_rig.blend> HealerBrawler_R15_v2.blend
python3 render_reviews.py HealerBrawler_R15_v2.blend renders_v2
python3 make_compare.py renders renders_v2 renders_v2/00_v1_vs_v2.png
```
