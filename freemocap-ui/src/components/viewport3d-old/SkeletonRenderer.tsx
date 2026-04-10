import {useEffect, useMemo, useRef} from "react";
import {
    BufferAttribute,
    BufferGeometry,
    InstancedMesh,
    LineBasicMaterial,
    LineSegments,
    MeshStandardMaterial,
    Object3D,
    SphereGeometry,
    Vector3,
} from "three";
import {useFrame} from "@react-three/fiber";
import {useServer} from "@/services";
import {Point3d, PointStyle} from "@/components/viewport3d/helpers/viewport3d-types";
import {
    getPointStyle,
    MAX_POINTS,
    MAX_SEGMENTS,
    SEGMENT_COLORS,
    SEGMENT_DEFINITIONS,
    Z_OFFSET,
} from "@/components/viewport3d/skeleton-config";
import {resolvePoint} from "@/components/viewport3d/virtual-points";
import {SKELETON_COLORS} from "@/components/viewport3d/skeleton-colors";

const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(10000, 10000, 10000);

/**
 * Renders the 3D skeleton using an InstancedMesh for landmark points
 * and LineSegments for bone connections. Subscribes directly to the
 * server's tracked-points stream and updates only dirty instances
 * each frame to minimize GPU uploads.
 */
export function SkeletonRenderer() {
    const { subscribeToTrackedPoints } = useServer();
    // Mutable refs for frame-loop access without triggering React re-renders
    const instancedMeshRef = useRef<InstancedMesh>(null);
    const lineSegmentsRef = useRef<LineSegments>(null);
    const trackedPointsRef = useRef<Map<string, Point3d>>(new Map());
    const pointNameToIndexRef = useRef<Map<string, number>>(new Map());
    const indexToPointNameRef = useRef<Map<number, string>>(new Map());
    const cachedStylesRef = useRef<Map<string, PointStyle>>(new Map());
    const nextAvailableIndexRef = useRef<number>(0);
    const dirtyIndicesRef = useRef<Set<number>>(new Set());
    const needsLineUpdateRef = useRef<boolean>(false);

    // Shared geometry: unit sphere scaled per-instance
    const sphereGeometry = useMemo(() => new SphereGeometry(1, 10, 8), []);

    // White base material — per-instance color tints it
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({
        color: '#ffffff',
        roughness: 0.35,
        metalness: 0.5,
    }), []);

    // Vertex-colored line material for skeleton segments
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

    // Assign a stable instance index and cache the point style for a new point name
    const assignIndex = (pointName: string): number => {
        if (nextAvailableIndexRef.current >= MAX_POINTS) {
            throw new Error(`Maximum tracked points (${MAX_POINTS}) exceeded for point "${pointName}"`);
        }
        const index = nextAvailableIndexRef.current++;
        pointNameToIndexRef.current.set(pointName, index);
        indexToPointNameRef.current.set(index, pointName);
        cachedStylesRef.current.set(pointName, getPointStyle(pointName));
        return index;
    };

    // Subscribe to tracked-points stream, mark dirty indices for changed/new/removed points
    useEffect(() => {
        const unsubscribe = subscribeToTrackedPoints((newPoints: Map<string, Point3d>) => {
            const prevPoints = trackedPointsRef.current;
            trackedPointsRef.current = newPoints;
            needsLineUpdateRef.current = true;

            for (const [pointName, point] of newPoints) {
                if (!pointNameToIndexRef.current.has(pointName)) {
                    const newIndex = assignIndex(pointName);
                    dirtyIndicesRef.current.add(newIndex);
                } else {
                    const prevPoint = prevPoints.get(pointName);
                    if (!prevPoint ||
                        prevPoint.x !== point.x ||
                        prevPoint.y !== point.y ||
                        prevPoint.z !== point.z) {
                        dirtyIndicesRef.current.add(pointNameToIndexRef.current.get(pointName)!);
                    }
                }
            }

            // Mark removed points as dirty so they get hidden
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

    // Initialize all instances as hidden on mount
    useEffect(() => {
        if (!instancedMeshRef.current) return;
        const mesh = instancedMeshRef.current;

        for (let i = 0; i < MAX_POINTS; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
            mesh.setColorAt(i, SKELETON_COLORS.hidden);
        }
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        mesh.count = MAX_POINTS;
    }, []);

    // Per-frame update: apply dirty point transforms and refresh line segment positions
    useFrame(() => {
        // Update dirty point instances
        if (instancedMeshRef.current && dirtyIndicesRef.current.size > 0) {
            const mesh = instancedMeshRef.current;
            const points = trackedPointsRef.current;

            for (const index of dirtyIndicesRef.current) {
                const pointName = indexToPointNameRef.current.get(index);

                if (pointName && points.has(pointName)) {
                    const point = points.get(pointName)!;
                    const style = cachedStylesRef.current.get(pointName)!;

                    DUMMY.position.set(point.x, point.y, point.z + Z_OFFSET);
                    DUMMY.scale.set(style.scale, style.scale, style.scale);
                    mesh.setColorAt(index, style.color);
                } else {
                    DUMMY.position.copy(FAR_AWAY);
                    DUMMY.scale.set(0, 0, 0);
                    mesh.setColorAt(index, SKELETON_COLORS.hidden);
                }

                DUMMY.updateMatrix();
                mesh.setMatrixAt(index, DUMMY.matrix);
            }

            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            dirtyIndicesRef.current.clear();
        }

        // Update line segment vertex positions
        if (lineSegmentsRef.current && needsLineUpdateRef.current) {
            const points = trackedPointsRef.current;
            const positions = lineGeometry.attributes.position.array as Float32Array;
            const colors = lineGeometry.attributes.color.array as Float32Array;
            let segmentIndex = 0;

            for (const segment of Object.values(SEGMENT_DEFINITIONS)) {
                const proximal = resolvePoint(points, segment.proximal);
                const distal = resolvePoint(points, segment.distal);
                const segColor = SEGMENT_COLORS[segmentIndex];
                const baseIdx = segmentIndex * 6;

                if (proximal && distal) {
                    positions[baseIdx]     = proximal.x;
                    positions[baseIdx + 1] = proximal.y;
                    positions[baseIdx + 2] = proximal.z + Z_OFFSET;

                    positions[baseIdx + 3] = distal.x;
                    positions[baseIdx + 4] = distal.y;
                    positions[baseIdx + 5] = distal.z + Z_OFFSET;

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
            needsLineUpdateRef.current = false;
        }
    });

    return (
        <>
            {/* Per-instance colored landmark points */}
            <instancedMesh
                ref={instancedMeshRef}
                args={[sphereGeometry, sphereMaterial, MAX_POINTS]}
                frustumCulled={false}
            />

            {/* Vertex-colored skeleton segments */}
            <lineSegments
                ref={lineSegmentsRef}
                geometry={lineGeometry}
                material={lineMaterial}
                frustumCulled={false}
            />
        </>
    );
}
