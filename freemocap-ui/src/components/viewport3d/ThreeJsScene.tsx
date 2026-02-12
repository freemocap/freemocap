import {useEffect, useMemo, useRef} from "react";
import {
    CameraHelper,
    InstancedMesh,
    MeshStandardMaterial,
    PerspectiveCamera,
    SphereGeometry,
    Object3D,
    Vector3,
    Color,
    BufferGeometry,
    BufferAttribute,
    LineBasicMaterial,
    LineSegments
} from "three";
import {extend, useFrame} from "@react-three/fiber";
import {CameraControls, Grid} from "@react-three/drei";
import {useServer} from "@/services";

extend({CameraHelper});

const MAX_POINTS = 1000;
const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(10000, 10000, 10000);

interface Point3d {
    x: number;
    y: number;
    z: number;
}

// --- Color palette (matches 2D overlay) ---

const COLORS = {
    left:       new Color('#4488FF'),
    right:      new Color('#FF4444'),
    center:     new Color('#00AA00'),
    leftHand:   new Color('#00FFFF'),
    rightHand:  new Color('#FF00FF'),
    face:       new Color('#FFD700'),
    hidden:     new Color('#000000'),
} as const;

// --- Point style: color + sphere scale per body part ---

interface PointStyle {
    color: Color;
    scale: number;
}

function getPointStyle(name: string): PointStyle {
    // Face landmarks
    if (name.startsWith('face.')) {
        return { color: COLORS.face, scale: 0.15 };
    }

    // Hand landmarks
    if (name.startsWith('left_hand.')) {
        return { color: COLORS.leftHand, scale: 0.125 };
    }
    if (name.startsWith('right_hand.')) {
        return { color: COLORS.rightHand, scale: 0.125 };
    }

    // Body — eyes, ears, mouth are small
    if (name.includes('eye') || name.includes('ear') || name.includes('mouth')) {
        const side = name.includes('left') ? COLORS.left : name.includes('right') ? COLORS.right : COLORS.center;
        return { color: side, scale: 0.2 };
    }

    // Body — fingers at wrist level
    if (name.includes('pinky') || name.includes('index') || name.includes('thumb')) {
        const side = name.includes('left') ? COLORS.left : COLORS.right;
        return { color: side, scale: 0.25 };
    }

    // Body — feet
    if (name.includes('heel') || name.includes('foot_index') || name.includes('ankle')) {
        const side = name.includes('left') ? COLORS.left : COLORS.right;
        return { color: side, scale: 0.3 };
    }

    // Body — major joints (shoulder, elbow, wrist, hip, knee)
    if (name.includes('left')) {
        return { color: COLORS.left, scale: 0.4 };
    }
    if (name.includes('right')) {
        return { color: COLORS.right, scale: 0.4 };
    }

    // Center (nose, etc.)
    return { color: COLORS.center, scale: 0.35 };
}

// --- Segment color determined by segment name ---

function getSegmentColor(segmentName: string): Color {
    if (segmentName.startsWith('left_hand_'))  return COLORS.leftHand;
    if (segmentName.startsWith('right_hand_')) return COLORS.rightHand;
    if (segmentName.startsWith('left'))        return COLORS.left;
    if (segmentName.startsWith('right'))       return COLORS.right;
    return COLORS.center;
}

// --- Hand connection template (MediaPipe hand landmark topology) ---

const HAND_CONNECTIONS: [string, string][] = [
    // Thumb
    ['wrist', 'thumb_cmc'],
    ['thumb_cmc', 'thumb_mcp'],
    ['thumb_mcp', 'thumb_ip'],
    ['thumb_ip', 'thumb_tip'],
    // Index finger
    ['wrist', 'index_finger_mcp'],
    ['index_finger_mcp', 'index_finger_pip'],
    ['index_finger_pip', 'index_finger_dip'],
    ['index_finger_dip', 'index_finger_tip'],
    // Middle finger
    ['wrist', 'middle_finger_mcp'],
    ['middle_finger_mcp', 'middle_finger_pip'],
    ['middle_finger_pip', 'middle_finger_dip'],
    ['middle_finger_dip', 'middle_finger_tip'],
    // Ring finger
    ['wrist', 'ring_finger_mcp'],
    ['ring_finger_mcp', 'ring_finger_pip'],
    ['ring_finger_pip', 'ring_finger_dip'],
    ['ring_finger_dip', 'ring_finger_tip'],
    // Pinky
    ['wrist', 'pinky_mcp'],
    ['pinky_mcp', 'pinky_pip'],
    ['pinky_pip', 'pinky_dip'],
    ['pinky_dip', 'pinky_tip'],
    // Palm
    ['index_finger_mcp', 'middle_finger_mcp'],
    ['middle_finger_mcp', 'ring_finger_mcp'],
    ['ring_finger_mcp', 'pinky_mcp'],
];

// Generate hand segment definitions for both hands
function buildHandSegments(handPrefix: string): Record<string, {proximal: string; distal: string}> {
    const segments: Record<string, {proximal: string; distal: string}> = {};
    HAND_CONNECTIONS.forEach(([proximal, distal], i) => {
        segments[`${handPrefix}_seg_${i}`] = {
            proximal: `${handPrefix}.${proximal}`,
            distal: `${handPrefix}.${distal}`,
        };
    });
    return segments;
}

// --- Segment definitions: body + both hands ---

const SEGMENT_DEFINITIONS: Record<string, {proximal: string; distal: string}> = {
    // Body
    head:               { proximal: "body.left_ear",        distal: "body.right_ear" },
    neck:               { proximal: "head_center",          distal: "neck_center" },
    spine:              { proximal: "neck_center",          distal: "hips_center" },
    right_shoulder:     { proximal: "neck_center",          distal: "body.right_shoulder" },
    left_shoulder:      { proximal: "neck_center",          distal: "body.left_shoulder" },
    right_upper_arm:    { proximal: "body.right_shoulder",  distal: "body.right_elbow" },
    left_upper_arm:     { proximal: "body.left_shoulder",   distal: "body.left_elbow" },
    right_forearm:      { proximal: "body.right_elbow",     distal: "body.right_wrist" },
    left_forearm:       { proximal: "body.left_elbow",      distal: "body.left_wrist" },
    right_hand_body:    { proximal: "body.right_wrist",     distal: "body.right_index" },
    left_hand_body:     { proximal: "body.left_wrist",      distal: "body.left_index" },
    right_pelvis:       { proximal: "hips_center",          distal: "body.right_hip" },
    left_pelvis:        { proximal: "hips_center",          distal: "body.left_hip" },
    right_thigh:        { proximal: "body.right_hip",       distal: "body.right_knee" },
    left_thigh:         { proximal: "body.left_hip",        distal: "body.left_knee" },
    right_shank:        { proximal: "body.right_knee",      distal: "body.right_ankle" },
    left_shank:         { proximal: "body.left_knee",       distal: "body.left_ankle" },
    right_foot:         { proximal: "body.right_ankle",     distal: "body.right_foot_index" },
    left_foot:          { proximal: "body.left_ankle",      distal: "body.left_foot_index" },
    right_heel:         { proximal: "body.right_ankle",     distal: "body.right_heel" },
    left_heel:          { proximal: "body.left_ankle",      distal: "body.left_heel" },
    right_foot_bottom:  { proximal: "body.right_heel",      distal: "body.right_foot_index" },
    left_foot_bottom:   { proximal: "body.left_heel",       distal: "body.left_foot_index" },
    // Hands
    ...buildHandSegments('right_hand'),
    ...buildHandSegments('left_hand'),
};

const MAX_SEGMENTS = Object.keys(SEGMENT_DEFINITIONS).length;

// Pre-compute segment colors (static)
const SEGMENT_COLORS: Color[] = Object.keys(SEGMENT_DEFINITIONS).map(getSegmentColor);

export function ThreeJsScene() {
    const { connectedCameraIds, subscribeToTrackedPoints } = useServer();
    const instancedMeshRef = useRef<InstancedMesh>(null);
    const lineSegmentsRef = useRef<LineSegments>(null);
    const cameraRefs = useRef<PerspectiveCamera[]>([]);

    // Performance-critical: direct refs to avoid React re-renders
    const trackedPointsRef = useRef<Map<string, Point3d>>(new Map());
    const pointNameToIndexRef = useRef<Map<string, number>>(new Map());
    const nextAvailableIndexRef = useRef<number>(0);
    const dirtyIndicesRef = useRef<Set<number>>(new Set());
    const needsLineUpdate = useRef<boolean>(false);

    // Unit sphere — per-instance scale controls visible size
    const sphereGeometry = useMemo(() => new SphereGeometry(1, 10, 8), []);

    // White base material so per-instance color shows through
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({
        color: '#ffffff',
        roughness: 0.35,
        metalness: 0.5,
    }), []);

    // Vertex-colored line material
    const lineMaterial = useMemo(() => new LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
    }), []);

    // Pre-allocated line geometry with position + color buffers
    const lineGeometry = useMemo(() => {
        const geometry = new BufferGeometry();
        const numVerts = MAX_SEGMENTS * 2;
        const positions = new Float32Array(numVerts * 3);
        const colors = new Float32Array(numVerts * 3);

        for (let i = 0; i < MAX_SEGMENTS; i++) {
            const segColor = SEGMENT_COLORS[i];
            for (let v = 0; v < 2; v++) {
                const vi = (i * 2 + v) * 3;
                positions[vi]     = 10000;
                positions[vi + 1] = 10000;
                positions[vi + 2] = 10000;
                colors[vi]     = segColor.r;
                colors[vi + 1] = segColor.g;
                colors[vi + 2] = segColor.b;
            }
        }

        geometry.setAttribute('position', new BufferAttribute(positions, 3));
        geometry.setAttribute('color', new BufferAttribute(colors, 3));
        return geometry;
    }, []);

    // Helper: calculate virtual midpoints
    const calculateVirtualPoint = (points: Map<string, Point3d>, virtualName: string): Point3d | null => {
        switch (virtualName) {
            case "head_center": {
                const l = points.get("body.left_ear");
                const r = points.get("body.right_ear");
                if (!l || !r) return null;
                return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2, z: (l.z + r.z) / 2 };
            }
            case "neck_center": {
                const l = points.get("body.left_shoulder");
                const r = points.get("body.right_shoulder");
                if (!l || !r) return null;
                return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2, z: (l.z + r.z) / 2 };
            }
            case "hips_center": {
                const l = points.get("body.left_hip");
                const r = points.get("body.right_hip");
                if (!l || !r) return null;
                return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2, z: (l.z + r.z) / 2 };
            }
            default:
                return points.get(virtualName) || null;
        }
    };

    // Subscribe to tracked points updates
    useEffect(() => {
        const unsubscribe = subscribeToTrackedPoints((newPoints: Map<string, Point3d>) => {
            const prevPoints = trackedPointsRef.current;
            trackedPointsRef.current = newPoints;
            needsLineUpdate.current = true;

            for (const [pointName, point] of newPoints) {
                if (!pointNameToIndexRef.current.has(pointName)) {
                    if (nextAvailableIndexRef.current >= MAX_POINTS) {
                        console.error(`Maximum points (${MAX_POINTS}) exceeded!`);
                        continue;
                    }
                    const newIndex = nextAvailableIndexRef.current++;
                    pointNameToIndexRef.current.set(pointName, newIndex);
                    dirtyIndicesRef.current.add(newIndex);
                } else {
                    const prevPoint = prevPoints.get(pointName);
                    if (!prevPoint ||
                        prevPoint.x !== point.x ||
                        prevPoint.y !== point.y ||
                        prevPoint.z !== point.z) {
                        const index = pointNameToIndexRef.current.get(pointName)!;
                        dirtyIndicesRef.current.add(index);
                    }
                }
            }

            for (const [pointName] of prevPoints) {
                if (!newPoints.has(pointName)) {
                    const index = pointNameToIndexRef.current.get(pointName);
                    if (index !== undefined) {
                        dirtyIndicesRef.current.add(index);
                    }
                }
            }
        });

        return unsubscribe;
    }, [subscribeToTrackedPoints]);

    // Initialize all instances hidden
    useEffect(() => {
        if (!instancedMeshRef.current) return;
        const mesh = instancedMeshRef.current;

        for (let i = 0; i < MAX_POINTS; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
            mesh.setColorAt(i, COLORS.hidden);
        }
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        mesh.count = MAX_POINTS;
    }, []);

    // Render loop — update positions, scales, colors, lines
    useFrame(() => {
        cameraRefs.current.forEach(camera => {
            if (camera) camera.lookAt(0, 0, 0);
        });

        const scale = 1;

        // Update points
        if (instancedMeshRef.current && dirtyIndicesRef.current.size > 0) {
            const mesh = instancedMeshRef.current;
            const points = trackedPointsRef.current;
            const nameToIndex = pointNameToIndexRef.current;

            for (const index of dirtyIndicesRef.current) {
                // Reverse-lookup the point name for this index
                let pointName: string | null = null;
                for (const [name, idx] of nameToIndex) {
                    if (idx === index) {
                        pointName = name;
                        break;
                    }
                }

                if (pointName && points.has(pointName)) {
                    const point = points.get(pointName)!;
                    const style = getPointStyle(pointName);

                    DUMMY.position.set(
                        point.x * scale,
                        point.y * scale,
                        (point.z - 15) * scale
                    );
                    DUMMY.scale.set(style.scale, style.scale, style.scale);
                    mesh.setColorAt(index, style.color);
                } else {
                    DUMMY.position.copy(FAR_AWAY);
                    DUMMY.scale.set(0, 0, 0);
                    mesh.setColorAt(index, COLORS.hidden);
                }

                DUMMY.updateMatrix();
                mesh.setMatrixAt(index, DUMMY.matrix);
            }

            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            dirtyIndicesRef.current.clear();
        }

        // Update line segments with vertex colors
        if (lineSegmentsRef.current && needsLineUpdate.current) {
            const points = trackedPointsRef.current;
            const positions = lineGeometry.attributes.position.array as Float32Array;
            const colors = lineGeometry.attributes.color.array as Float32Array;
            let segmentIndex = 0;

            for (const [_segmentName, segment] of Object.entries(SEGMENT_DEFINITIONS)) {
                const proximalPoint = calculateVirtualPoint(points, segment.proximal);
                const distalPoint = calculateVirtualPoint(points, segment.distal);
                const segColor = SEGMENT_COLORS[segmentIndex];
                const baseIdx = segmentIndex * 6;

                if (proximalPoint && distalPoint) {
                    positions[baseIdx]     = proximalPoint.x * scale;
                    positions[baseIdx + 1] = proximalPoint.y * scale;
                    positions[baseIdx + 2] = (proximalPoint.z - 15) * scale;

                    positions[baseIdx + 3] = distalPoint.x * scale;
                    positions[baseIdx + 4] = distalPoint.y * scale;
                    positions[baseIdx + 5] = (distalPoint.z - 15) * scale;

                    colors[baseIdx]     = segColor.r;
                    colors[baseIdx + 1] = segColor.g;
                    colors[baseIdx + 2] = segColor.b;
                    colors[baseIdx + 3] = segColor.r;
                    colors[baseIdx + 4] = segColor.g;
                    colors[baseIdx + 5] = segColor.b;
                } else {
                    for (let i = 0; i < 6; i++) {
                        positions[baseIdx + i] = 10000;
                    }
                }

                segmentIndex++;
            }

            lineGeometry.attributes.position.needsUpdate = true;
            lineGeometry.attributes.color.needsUpdate = true;
            needsLineUpdate.current = false;
        }
    });

    return (
        <>
            <CameraControls makeDefault/>

            <ambientLight intensity={0.6}/>
            <directionalLight
                castShadow
                position={[5, 5, 5]}
                intensity={0.5}
                shadow-mapSize={1024}
            />
            {/* Fill light from below to prevent pure-black undersides */}
            <directionalLight
                position={[-3, -2, -3]}
                intensity={0.15}
            />

            <Grid
                renderOrder={-1}
                position={[0, -0.01, 0]}
                infiniteGrid
                cellSize={1}
                cellThickness={0.5}
                sectionSize={3}
                sectionThickness={1}
                //@ts-ignore
                sectionColor={[0.25, 0, 0.25]}
                fadeDistance={100}
            />

            <axesHelper/>

            {/* Per-instance colored points */}
            <instancedMesh
                ref={instancedMeshRef}
                args={[sphereGeometry, sphereMaterial, MAX_POINTS]}
                frustumCulled={false}
            />

            {/* Vertex-colored line segments */}
            <lineSegments
                ref={lineSegmentsRef}
                geometry={lineGeometry}
                material={lineMaterial}
                frustumCulled={false}
            />
        </>
    );
}