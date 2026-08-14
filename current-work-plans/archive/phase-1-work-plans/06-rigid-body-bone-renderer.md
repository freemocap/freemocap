# FMC-RB — RigidBody Bone Renderer (3JS canonical bone visualization)

> **Parallel track — requires FMC-WS-4 (rotations on the wire) to activate.**
> Renders the canonical bone model driven by quaternions from the orientation solver.
> This is the VMC/streaming bone representation — wholly separate from the tracker
> keypoints + connections display (which stays as-is for triangulated keypoint viz).
> **Status: plan — executable detail below.**

## Motivation

The existing 3D viewport renders tracker keypoints as dots (`KeypointsRenderer`) and
tracker connections as stick-figure lines (`ConnectionRenderer`). Those show the
triangulated keypoints from skellytracker. They stay.

The rigid body bone renderer is a **separate layer** that visualizes the canonical bone
model — the orientation solver's output. These are the bones that will be streamed via
VMC and similar protocols: defined by position, world-frame orientation, and the
canonical bone hierarchy from `StandardHuman`. Every bone is driven by its world
quaternion from the solver. Identity quaternion = T-pose (bone points along its
reference direction).

## Design: what it looks like

Following the Blender addon's `make_bone_mesh()` (`freemocap_blender_addon/
core_functions/meshes/rigid_body_meshes/helpers/make_bone_mesh.py`):

- **Shape**: truncated cone (body) + sphere (proximal joint), merged into one mesh
- **Asymmetry**: elliptical cross-section — squished ~60% on local X so roll/twist is
  visible (a circular cone rotated around its long axis looks identical at every roll angle)
- **Color**: red = right side, blue = left side, green = center/trunk
- **Scale**: each bone instance scaled to its segment length along the long axis
- **Orientation**: driven by the solver's world quaternion (from `subscribeToRotations`)
- **Position**: at the bone's proximal joint center (from the standard stream's POINTS block)

## Data sources (all canonical, no tracker data)

| Data | Source | When available |
|---|---|---|
| Bone names | `stream_schema.joint_hierarchy` keys (canonical: `left_upper_arm`, `spine`, etc.) | After FMC-WS-4 (schema on connect) |
| Bone pairings | `stream_schema.joint_hierarchy` — parent→children edges define bone segments | After FMC-WS-4 |
| Bone positions | `subscribeToSkeleton` on the standard-stream POINTS block — canonical bone proximal joint centers from the solver | After FMC-WS-4 |
| Bone orientations | `subscribeToRotations` — `ROTATIONS_WORLD` block, wxyz quaternion per bone from the solver | After FMC-WS-4 |
| Bone colors | Derived from bone canonical name prefix (`left_` → blue, `right_` → red, else → green) | Always |

The renderer does NOT use `subscribeToSkeleton` from the legacy tracker path, nor tracker
`connections`, nor tracker keypoint names. Those are for the existing `KeypointsRenderer` /
`ConnectionRenderer` which remain unchanged.

## Why InstancedMesh

Same pattern as the existing `KeypointsRenderer`:

- **One `InstancedMesh`** for all bones (up to ~200: 55 VRM bones × 2 for multi-subject)
- **Per-instance colors** via `instanceColor`
- **Per-instance matrix** — encodes position + world quaternion + scale
- **One draw call** for the entire skeleton's rigid bodies
- **`frustumCulled={false}`** — same as KeypointsRenderer

## Files

| File | Action |
|---|---|
| `freemocap-ui/src/components/viewport3d/renderers/RigidBodyBoneRenderer.tsx` | **[new]** The renderer component. |
| `freemocap-ui/src/components/viewport3d/renderers/RigidBodyBoneGeometry.ts` | **[new]** Geometry factory — builds the shared elliptical cone+sphere `BufferGeometry` once. |
| `freemocap-ui/src/components/viewport3d/ThreeJsScene.tsx` | **[evolve]** Add `<RigidBodyBoneRenderer />`, gated by `visibility.rigidBodyBones`. |
| `freemocap-ui/src/components/viewport3d/helpers/viewport3d-types.ts` | **[evolve]** Add `rigidBodyBones` to `ViewportVisibility`. |

## Geometry: `RigidBodyBoneGeometry.ts`

```typescript
function createBoneMeshGeometry(): BufferGeometry {
    // ── Body: truncated cone, elliptical cross-section ──
    // CylinderGeometry(radiusTop, radiusBottom, height, radialSegments, heightSegments)
    //   radiusTop = 0.6    (narrower at distal end)
    //   radiusBottom = 1.0 (wider at proximal end — the "joint" area)
    //   height = 1.0       (unit height along +Z)
    //   radialSegments = 12
    //
    // Then squish X: for each vertex, vertex.x *= 0.55
    // Creates the elliptical cross-section that reveals roll.

    // ── Joint sphere: small sphere at Z=0 ──
    // SphereGeometry(radius=1.1, widthSegments=8, heightSegments=6)
    // Slightly wider than the cone base.

    // ── Merged via BufferGeometryUtils.mergeGeometries() ──
    // Total: ~150 vertices, ~300 triangles
}
```

## Renderer component

```typescript
// RigidBodyBoneRenderer.tsx

const MAX_BONES = 256;
const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(1e5, 1e5, 1e5);

// Scratch — zero allocation in hot path
const _pos = new Vector3();
const _quat = new Quaternion();
const _scl = new Vector3();
const SQUISH_X = 0.55;
const SQUISH_Y = 1.0;

type BoneSide = 'left' | 'right' | 'center';
const BONE_COLORS: Record<BoneSide, Color> = {
    left:   new Color('#4488FF'),
    right:  new Color('#FF4444'),
    center: new Color('#00AA00'),
};

function classifyBone(boneName: string): BoneSide {
    if (boneName.startsWith('left_'))  return 'left';
    if (boneName.startsWith('right_')) return 'right';
    return 'center';
}

export function RigidBodyBoneRenderer() {
    const geometry = useMemo(() => createBoneMeshGeometry(), []);
    const material = useMemo(() => new MeshBasicMaterial(), []);

    // ── Canonical data subscriptions (all from standard stream) ──
    const { subscribeToSkeleton, subscribeToRotations } = useKeypointsSource();
    // These now come from the standard stream's POINTS + ROTATIONS_WORLD blocks.

    const meshRef = useRef<InstancedMesh>(null);
    const skeletonRef = useRef<KeypointsFrame | null>(null);
    const rotationsRef = useRef<RotationsFrame | null>(null);
    const dirtyRef = useRef(false);

    // ── Bone index maps — built once when schema arrives ──
    // boneName → instance index
    // boneName → { proximalFrameIdx, distalFrameIdx } (from the schema's joint_hierarchy)
    const boneInstances = useRef<Map<string, {
        instanceIdx: number;
        proximalFrameIdx: number;  // index in skeleton interleaved array
        distalFrameIdx: number;
        side: BoneSide;
    }>>(new Map());

    // ── Initialize: hide all ──
    useEffect(() => {
        const mesh = meshRef.current!;
        for (let i = 0; i < MAX_BONES; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
        }
        mesh.instanceMatrix.needsUpdate = true;
    }, []);

    // ── Per-frame update ──
    useFrame(() => {
        if (!dirtyRef.current) return;
        const t0 = performance.now();
        const mesh = meshRef.current!;
        const skeleton = skeletonRef.current;
        const rotations = rotationsRef.current;
        if (!skeleton || !rotations) return;

        for (const [boneName, info] of boneInstances.current) {
            const pOff = info.proximalFrameIdx * 4;
            const dOff = info.distalFrameIdx * 4;
            const px = skeleton.interleaved[pOff];
            const py = skeleton.interleaved[pOff + 1];
            const pz = skeleton.interleaved[pOff + 2];
            const dx = skeleton.interleaved[dOff];
            const dy = skeleton.interleaved[dOff + 1];
            const dz = skeleton.interleaved[dOff + 2];
            const length = Math.sqrt((dx-px)**2 + (dy-py)**2 + (dz-pz)**2);

            // Look up world quaternion from rotations frame
            const boneIdx = rotations.boneNames.indexOf(boneName);
            if (boneIdx === -1 || length < 0.001) {
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
            } else {
                const rOff = boneIdx * 4;
                const qw = rotations.worldQuaternions[rOff];
                const qx = rotations.worldQuaternions[rOff + 1];
                const qy = rotations.worldQuaternions[rOff + 2];
                const qz = rotations.worldQuaternions[rOff + 3];

                _pos.set(px, py, pz);  // proximal joint
                _quat.set(qx, qy, qz, qw);  // Three.js is xyzw
                _scl.set(SQUISH_X * length, SQUISH_Y * length, length);

                DUMMY.position.copy(_pos);
                DUMMY.quaternion.copy(_quat);
                DUMMY.scale.copy(_scl);
                mesh.setColorAt(info.instanceIdx, BONE_COLORS[info.side]);
            }
            DUMMY.updateMatrix();
            mesh.setMatrixAt(info.instanceIdx, DUMMY.matrix);
        }

        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        dirtyRef.current = false;

        const elapsed = performance.now() - t0;
        if (elapsed > 8) console.warn(`RigidBodyBoneRenderer: ${elapsed.toFixed(1)}ms`);
    });

    return (
        <instancedMesh
            ref={meshRef}
            args={[geometry, material, MAX_BONES]}
            frustumCulled={false}
        />
    );
}
```

## Bone index map: built from schema, not tracker connections

When the `stream_schema` arrives, the renderer builds `boneInstances` once:

```typescript
function buildBoneInstances(
    schema: StreamSchema,
    skeletonPointNames: readonly string[],
): Map<string, BoneInstance> {
    const map = new Map();
    let nextIdx = 0;

    // Walk joint_hierarchy to find parent→child bone edges
    for (const [parentName, children] of Object.entries(schema.joint_hierarchy)) {
        if (parentName === '__root__') continue;
        for (const childName of children) {
            const proximalIdx = skeletonPointNames.indexOf(parentName);
            const distalIdx = skeletonPointNames.indexOf(childName);
            if (proximalIdx === -1 || distalIdx === -1) continue;

            const boneName = parentName;  // bone is named by its proximal joint
            map.set(boneName, {
                instanceIdx: nextIdx++,
                proximalFrameIdx: proximalIdx,
                distalFrameIdx: distalIdx,
                side: classifyBone(boneName),
            });
        }
    }
    return map;
}
```

The key: `joint_hierarchy` uses canonical bone names (`hips`, `spine`, `left_upper_arm`, …).
The POINTS block in the standard stream uses the same canonical names. So the mapping is
direct — no `_BONE_TO_LANDMARK` bridge needed at the frontend layer.

## Performance budget

| Metric | Target | How |
|---|---|---|
| Draw calls | 1 | Single `InstancedMesh` with per-instance colors |
| Vertices | ~150 shared | Low-poly cone (12×4) + sphere (8×6) |
| Instances | ≤256 | 55 VRM bones + multi-subject headroom |
| per-frame CPU | <2ms | Reused scratch objects, no allocations |
| per-frame GC | 0 | All scratch allocated once via `useRef` |

## Task checklist

1. [ ] **Write `RigidBodyBoneGeometry.ts`** — `createBoneMeshGeometry()`: truncated elliptical
      cone + proximal sphere, merged. Unit test: vertex count, Z bounds at 0..1.
2. [ ] **Write `classifyBone()`** — left/right/center from canonical bone name prefix.
3. [ ] **Write `buildBoneInstances()`** — from `StreamSchema.joint_hierarchy` + POINTS
      block point names → bone instance index map.
4. [ ] **Write `RigidBodyBoneRenderer.tsx`** — single `InstancedMesh`, `DUMMY Object3D`
      pattern (following `KeypointsRenderer`), driven by `subscribeToSkeleton` (standard-stream
      POINTS) + `subscribeToRotations` (standard-stream ROTATIONS_WORLD).
5. [ ] **Wire into `ThreeJsScene.tsx`** — `<RigidBodyBoneRenderer />` gated by
      `visibility.rigidBodyBones`.
6. [ ] **Add visibility toggle** — `rigidBodyBones: true` in `ViewportVisibility` +
      `DEFAULT_VISIBILITY`.
7. [ ] **Schema-change handling** — rebuild `boneInstances` when `stream_schema` changes
      (content comparison on `joint_hierarchy` keys).
8. [ ] **Smoke test** — run the app with standard stream flowing (after FMC-WS-2/4),
      verify cone+sphere meshes on every bone, colored left=blue/right=red/center=green,
      oriented by solver quaternions.

## Tests

- `test_createBoneMeshGeometry` — vertex count within bounds, Z range 0..1, X asymmetry.
- `test_classifyBone` — `left_upper_arm` → left, `right_upper_leg` → right, `spine` → center.
- `test_buildBoneInstances` — given a `joint_hierarchy` + point names, correctly maps bone
  names to frame indices and instance slots.

## NOT in scope

- Bone mesh variant shapes (flat bones for pelvis/scapula). All bones use the same geometry.
- Per-bone twist-policy color-coding. Nice-to-have follow-up.
- The existing `KeypointsRenderer` and `ConnectionRenderer` — they stay exactly as they are.
  This is a separate rendering layer for the canonical bone model.
