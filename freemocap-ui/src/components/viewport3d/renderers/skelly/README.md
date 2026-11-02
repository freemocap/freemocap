# Skelly artwork in the viewer

Open a live reconstruction or a recorded reconstruction, then enable **Tracked
model → Skelly mesh** in the viewport layers. The layer starts off. Keep **Bones**
and **Landmarks** visible for comparison, or hide Bones to see the artwork alone.
Scrub playback, pause/resume, and compare motion and fitted proportions. Check
the skull, thorax, pelvis and hands, then inspect missing observations and a
change of recording/model. The generic model layers remain independent.

The current head-only polish trial uses 90% of the original skull artwork size,
uniformly about the existing skull attachment origin. This changes only mesh
vertices during preparation, not the scientific head landmarks, subject scale,
pose or cervical attachment transform. Pelvis and torso artwork are unchanged.
Compare the skull against Landmarks with Bones temporarily hidden; tilt/turn the
head and inspect the neck connection. This is a reversible visual trial, not an
anatomical soft-tissue estimate. `SKULL_ARTWORK_SCALE` in the preparation tool and
the generated `artworkScales` metadata record the intentional addon difference.

The torso now has a separate **attachment-based artwork correction**. The
addon's `upper_arm.L/R_origin` helpers identify shoulder joint centers (the same
semantics used by its rest-pose empty markers). The original torso-length fit
placed these anchors too close together and anterior to the model's shoulder
origins. Preparation moves each side toward its model rest attachment, with
displacement proportional to lateral distance from the spine. The centerline,
including chest and neck anchors, stays fixed. `torsoSocketFit` records both
sets of anchors; no mesh bounding-box target or arbitrary torso multiplier is
used. This is an explicit improvement over the addon's native uniform-length
fit, not a claim that its current implementation already performs this step.

The correction is baked into the artwork once. Existing per-frame segment
poses/scales are unchanged; no new rig or vertex update loop is added. A rigid
thorax still cannot follow independently moving clavicles perfectly, and
different independently fitted clavicle proportions can leave residual gaps.
Review with arms resting, then extended, and with one shoulder raised: compare
the scapula/humerus connection while checking that the central neck and lower
torso attachment have not shifted. Skull size remains at the accepted 90% fit.

This is the addon's existing Skelly artwork fitted to the established Forge
standard-human definition. It is not a new pose solver or a generic humanoid
retargeter. The binding checks model rest landmarks, hierarchy, world-rest
orientations and authored lengths. A model with different authored geometry
does not use this artwork; use its generic Bones/landmark layers. Fitted subject
segment lengths can vary normally and update the rigid part scales without
rebuilding vertices. Unavailable poses or invalid fitted scales hide the
affected artwork part.

`SkellyMeshRenderer` uses the same resolved model-frame source as the existing
rigid renderer, including the viewport worker and recording playback. There is
no new server channel, addon runtime import or alternative skeleton hierarchy.
The three-material mesh has 55 independent bones with one rigid weight per
vertex. World rotations already contain the rest orientation; the renderer
does not apply it again. Existing frame-buffer ownership remains unchanged.

## Source and regeneration

`skelly.json` is an intentional production asset. Its source is the sibling
`freemocap_blender_addon` checkout's
`freemocap_blender_addon/assets/skelly_mesh.json.gz`, itself extracted from
`assets/skelly_full_mesh_20k_faces.blend`. The payload records the source SHA256.
The source artwork remains editable in the addon, not in this generated file.

The offline preparation tool reads the addon's existing `asset_segments` mapping
and canonical attachment metadata. It reproduces `parquet_scene.native_skelly`
and `attachment_frame.attachment_rotation` using the installed editable Forge's
public model/rest-pose interfaces. Source-origin alignment, roll/secondary
landmarks and the pelvis-width rule are preserved. Three concave source polygons
require triangulation; flat-shaded faces have separate vertices. Source material
colors, metalness, roughness, emission and alpha are retained. Three.js and
Blender lighting/BRDF output are not claimed to be pixel-identical.

From the Core checkout, with outputs verified as ignored:

```powershell
.venv/Scripts/python.exe -B freemocap-ui/tools/prepare-skelly-asset.py --addon-root ../freemocap_blender_addon --output .test-artifacts/skelly/skelly.json --reference-model .test-artifacts/skelly/reference-model.json
```

Review the generated asset and reference checks before copying it to this
directory. Do not edit Forge's model or rest pose to make artwork fit.

The addon repository declares AGPLv3. Its `DEPENDENCIES.md` still calls out
asset-provenance review; independent artwork attribution/licensing has not been
established here. This implementation does not claim release/distribution
clearance for a separately published asset package.

## Verification

From `freemocap-ui`, bundle `skelly-binding.test.ts` with esbuild for Node and run
the result with `node --test`. Use an ignored `.test-artifacts/skelly/` output.
The tests exercise current geometry compatibility, sign-equivalent quaternions,
known rigid transforms, differing lengths, missing data, reordered rows, model
replacement and geometry/material/bone-texture disposal. They also print CPU
transform preparation timing, explicitly excluding WebGL/GPU time.

Run `tools/test_prepare_skelly_asset.py` with Core's Python for shoulder-anchor
checks. They verify exact symmetric/asymmetric target attachment, fixed
centerline, unchanged inputs, unit/scale covariance and invalid-anchor rejection.
The Blender oracle compares its original fit plus the declared skull and torso
artwork corrections; it does not silently redefine the reference algorithm.

`tools/check-skelly-blender.py` runs inside an existing Blender with
`--background --factory-startup --python-exit-code 1`. After `--`, supply addon
root, generated reference-model JSON and prepared asset JSON. It executes the
actual addon fitting functions without addon registration or saved-scene writes,
then compares every mapped original vertex.

`node tools/check-skelly-web.mjs` renders the deterministic fixture with CPU
SwiftShader. It checks compatibility against the actual Core server projection,
asserts three draw calls and 20,432 triangles, and writes its screenshot and
report under `.test-artifacts/skelly/`. Set `SKELLY_TEST_BROWSER` if the default
Windows Edge executable is not available. It starts no app server or cameras.

Initial checks: five focused tests, TypeScript, eleven existing worker-transfer
tests and Vite build passed. Blender 5.2.2 comparisons covered all 55 parts with
maximum error `5.28e-8` authored units. The software browser fixture rendered the
full model. Live-camera quality, actual hardware frame rate and human visual
acceptance remain running-app checks; software rendering is not a GPU benchmark.

## Separate VRM recommendation

Keep Skelly VRM export as a separate deliverable. Forge already defines the
humanoid hierarchy, rest pose and coordinate conventions, including the existing
VRM reference. A VRM export would adapt this artwork to the chosen humanoid
avatar contract and validate it in a receiver; it must not change the scientific
model to satisfy an avatar. Neither this native viewer layer nor VMC transmission
requires a custom Skelly VRM asset.
