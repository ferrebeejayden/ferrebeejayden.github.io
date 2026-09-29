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

---

## v3: shoulder connection, feminine hair, material depth

`HealerBrawler_R15_v3.blend` is built by `build_healer_brawler_v3.py`. v1 and v2 are unchanged.
The v2 proportions are kept (narrow shoulders, waist, bust, slim lower body, coat taper).

- **Shoulder connection:** the sleeve cap is set in. Its inner side reaches over the coat's shoulder
  line (`reach` in `sleeve_ring`), so the sleeve grows out of the shoulder instead of hanging beside
  it. A darker armhole seam ridge marks the join. Weights: the inner cap blends up to 78% into
  `UpperTorso` (`w_arm`), and the coat's shoulder edge blends 35% into `UpperArm` (`w_torso`). When
  the arm lifts, the cap stretches from the shoulder onto the arm like connected cloth. The limb
  blocks stay hidden inside the sleeve. Tested at neutral, 20°, 45°, 90° and one arm raised.
- **Hair (rebuilt):** a half-up style with:
  - a full crown cap (thicker, and covering the sides and the nape);
  - four soft layered bangs tucked under the crown;
  - wide side sections sweeping back into a tie;
  - a seven-lock back curtain covering the nape;
  - four face-framing strands (two cheek locks and two longer strands resting on the coat);
  - a large tied ponytail with two layered side locks.
  The gold band, jade-flower pin and beads sit at the tie. The small top bun is gone.
- **Material depth:** procedural, object-space shaders in `surface_shader`, used for the renders:
  - colour breakup;
  - woven bump (heavier on the sash, with horizontal compression lines);
  - large soft fold shading;
  - ambient occlusion in overlaps;
  - darkening at cuffs, hems, the knees and contact areas, driven by a per-vertex `wear` attribute;
  - rubbed, lighter edges, driven by a per-vertex `edge` attribute.

  Each surface responds differently: a matte robe, soft cloth for the inner top, heavier woven sash,
  leather boots with scuffed toes, metallic gold, skin with a touch of subsurface, and hair with a soft
  anisotropic sheen. The `wear`/`edge` attributes stay on the meshes so they can be baked into
  textures for Roblox later.
- **Cloth construction geometry:**
  - a rolled hem on every coat panel;
  - side seam ridges;
  - armhole seams and cuff piping;
  - thicker lapels and trim;
  - a hanging sash end under the knot;
  - a few large skirt folds;
  - one-segment bevels on hard rims, plus weighted normals.

About 82k triangles. The extra geometry is spent on the coat's construction, the hair and the bevels.

```
python3 build_healer_brawler_v3.py <blank_rig.blend> HealerBrawler_R15_v3.blend
python3 render_reviews.py HealerBrawler_R15_v3.blend renders_v3
python3 make_compare_v3.py <v2_renders_with_hair_silhouettes> renders_v3 renders_v3/00_v2_vs_v3.png
```

---

## v5: Roblox-first style correction

`HealerBrawler_R15_v5.blend` is built by `build_healer_brawler_v5.py`. v1–v3 are unchanged. (There is no
v4; the v5 comparison is against v3, the previous revision.)

The target is a **Roblox avatar first, anime character second**, so the gray model on its own has to
read as Roblox.

- **Body:** the full-size 1×1 R15 arm and leg blocks are back at their original positions, and the hands
  are simple blocks. The torso is a boxy block with broad square shoulders, a mild waist and readable
  hips. The bust is a stylised rounded form on the block's front rather than a human torso.
- **Sleeves:** clothing shells with a rounded-box cross-section built around the blocky arm. They have a
  square shoulder top with a softened edge, a slight flare, big soft folds, a strong cuff band and a gold
  stripe. The arm sits against the torso the Roblox way.
- **Robe:** sits over the block torso, eases in at the sash and flares to the hem. It has a bold front
  trim, a standing collar, split lower panels, a rolled hem and seams.
- **Wrapped top:** thicker cloth, a readable crossing, and bold lapels that narrow into the sash.
- **Sash:** chunky, readable layers (main band, slanted wrap and under-band), plus the cord, knot and
  hanging end.
- **Lower body:** boxy trousers over the blocky legs, chunky wraps, block boots.
- **Head and face:** a rounded-cube Roblox head. The face has large anime eyes, simple brows, a tiny
  nose mark and a small smile.
- **Hair:** chunky, faceted anime pieces with 6-sided locks and sharp edges:
  - a strong pointed fringe with an accent lock between the eyes;
  - big side masses;
  - two cheek locks and two long locks in front of the shoulders;
  - a long, layered back with a V-shaped hem;
  - a substantial high ponytail with two side locks.
  The gold band, jade-flower pin and beads sit at the tie.
- **Materials:** the v3 procedural material system (matte robe, soft wrap, woven sash, leather boots,
  metallic trim, wear and edge masks), now applied to the new forms.

The gray-model review renders are in `renders_v5/graybox/` (run with `HB_GRAY=1`); the final renders
are in `renders_v5/`.

```
python3 build_healer_brawler_v5.py <blank_rig.blend> HealerBrawler_R15_v5.blend
HB_GRAY=1 python3 render_reviews.py HealerBrawler_R15_v5.blend renders_v5/graybox
python3 render_reviews.py HealerBrawler_R15_v5.blend renders_v5
python3 make_compare_v5.py renders_v3 renders_v5 renders_v5/00_v3_vs_v5.png
```

---

## v6: hair-only rebuild

`HealerBrawler_R15_v6.blend` is built by `build_healer_brawler_v6.py`, which is identical to v5 except
for the hair meshes and the hair shader. The body, clothing, proportions, rig, weights and materials are
v5's. v5 is unchanged.

The hair is a half-up style built from primary masses, then secondary locks, then accents:

- **Base:** a thin scalp-coverage layer only, with no helmet shell. The silhouette comes from the locks.
- **Crown (primary):** six broad masses flow from a slightly off-centre part (`PART`) around the crown
  into the tie. The part and the flow direction are visible, and the lumpy, asymmetric crown avoids a
  sphere. Four upper-back locks sweep up from behind the ears into the tie.
- **Bangs (secondary):** four overlapping bangs of different lengths and directions: a long sweep to the
  wearer's right, a centre bang, a short left bang and an accent lock. They are kept close to the
  forehead, so there's no visor and no row of teeth.
- **Side volume (secondary):** broad temple/cheek masses that reach past the jaw. The right side is a
  little longer.
- **Face framing (accent):** two long locks resting on the robe front. The right one is longer.
- **Loose back (primary):** seven broad, overlapping locks of varied length (z ≈ 3.3–3.8), with late
  tapers and slight directional offsets. They lie on the robe back instead of forming a spike curtain.
- **Ponytail:** four locks gathered at the tie (main fall, left curve, right flip, short top flick),
  each curving on its own. The gold band, jade-flower pin and beads sit at the tie.
- **Shader:** each lock stores `hs` (0 at the root, 1 at the tip) and `lockvar` (a per-lock tone). The
  shader darkens roots and recesses, lightens the broad tips, varies the tone between overlapping locks,
  and adds a controlled anisotropic sheen with AO in the recesses.

Gray review renders (front, 3/4, side, rear 3/4, back, from above) are in `renders_v6/graybox/`. Final
renders are in `renders_v6/`, and `renders_v6/00_v5_vs_v6.png` is the comparison sheet.

```
python3 build_healer_brawler_v6.py <blank_rig.blend> HealerBrawler_R15_v6.blend
HB_GRAY=1 python3 render_reviews.py HealerBrawler_R15_v6.blend renders_v6/graybox 70_h_front 71_h_34 72_h_side 73_h_rear34 74_h_back 75_h_above
python3 render_reviews.py HealerBrawler_R15_v6.blend renders_v6
python3 make_compare_v6.py <v5_hair_renders> renders_v6 renders_v6/00_v5_vs_v6.png
```
