import {useEffect, useMemo, useRef} from "react";
import {
    CameraHelper,
    InstancedMesh,
    MeshStandardMaterial,
    PerspectiveCamera,
    SphereGeometry,
    Object3D,
    Matrix4,
    Vector3,
    BufferGeometry,
    BufferAttribute,
    LineBasicMaterial,
    LineSegments
} from "three";
import {extend, useFrame} from "@react-three/fiber";
import {CameraControls, Grid} from "@react-three/drei";
import {useServer} from "@/services";

extend({CameraHelper});

const MAX_POINTS = 1000; // Pre-allocate for max expected points
const POINT_SCALE = 1; // Scale points down since they're in meters
const DUMMY = new Object3D(); // Reusable dummy object for matrix updates

interface Point3d {
    x: number;
    y: number;
    z: number;
}

// Segment definitions with virtual points that need to be calculated
const SEGMENT_DEFINITIONS: Record<string, {proximal: string, distal: string}> = {
    head: { proximal: "body.left_ear", distal: "body.right_ear" },
    neck: { proximal: "head_center", distal: "neck_center" },
    spine: { proximal: "neck_center", distal: "hips_center" },
    right_shoulder: { proximal: "neck_center", distal: "body.right_shoulder" },
    left_shoulder: { proximal: "neck_center", distal: "body.left_shoulder" },
    right_upper_arm: { proximal: "body.right_shoulder", distal: "body.right_elbow" },
    left_upper_arm: { proximal: "body.left_shoulder", distal: "body.left_elbow" },
    right_forearm: { proximal: "body.right_elbow", distal: "body.right_wrist" },
    left_forearm: { proximal: "body.left_elbow", distal: "body.left_wrist" },
    right_hand: { proximal: "body.right_wrist", distal: "body.right_index" },
    left_hand: { proximal: "body.left_wrist", distal: "body.left_index" },
    right_pelvis: { proximal: "hips_center", distal: "body.right_hip" },
    left_pelvis: { proximal: "hips_center", distal: "body.left_hip" },
    right_thigh: { proximal: "body.right_hip", distal: "body.right_knee" },
    left_thigh: { proximal: "body.left_hip", distal: "body.left_knee" },
    right_shank: { proximal: "body.right_knee", distal: "body.right_ankle" },
    left_shank: { proximal: "body.left_knee", distal: "body.left_ankle" },
    right_foot: { proximal: "body.right_ankle", distal: "body.right_foot_index" },
    left_foot: { proximal: "body.left_ankle", distal: "body.left_foot_index" },
    right_heel: { proximal: "body.right_ankle", distal: "body.right_heel" },
    left_heel: { proximal: "body.left_ankle", distal: "body.left_heel" },
    right_foot_bottom: { proximal: "body.right_heel", distal: "body.right_foot_index" },
    left_foot_bottom: { proximal: "body.left_heel", distal: "body.left_foot_index" },
};

const MAX_SEGMENTS = Object.keys(SEGMENT_DEFINITIONS).length;

export function ThreeJsScene() {
    const { connectedCameraIds, subscribeToTrackedPoints } = useServer();
    const instancedMeshRef = useRef<InstancedMesh>(null);
    const lineSegmentsRef = useRef<LineSegments>(null);
    const cameraRefs = useRef<PerspectiveCamera[]>([]);

    // Performance-critical: Direct refs to avoid React re-renders
    const trackedPointsRef = useRef<Map<string, Point3d>>(new Map());
    const pointNameToIndexRef = useRef<Map<string, number>>(new Map());
    const nextAvailableIndexRef = useRef<number>(0);
    const dirtyIndicesRef = useRef<Set<number>>(new Set());
    const needsLineUpdate = useRef<boolean>(false);

    // Pre-create geometry and material once
    const sphereGeometry = useMemo(() => new SphereGeometry(0.4, 8, 6), []); // Bigger spheres
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({
        color: '#00ff66', // Brighter color for visibility
        roughness: 0.4,
        metalness: 0.6,
        emissive: '#00ff66',
        emissiveIntensity: 0.2
    }), []);

    // Create line material
    const lineMaterial = useMemo(() => new LineBasicMaterial({
        color: '#ffffff',
        linewidth: 2,
        transparent: true,
        opacity: 0.8
    }), []);

    // Create line geometry with pre-allocated buffer
    const lineGeometry = useMemo(() => {
        const geometry = new BufferGeometry();
        // Each segment needs 2 vertices (6 floats)
        const positions = new Float32Array(MAX_SEGMENTS * 2 * 3);
        // Initialize far away
        for (let i = 0; i < positions.length; i++) {
            positions[i] = 10000;
        }
        geometry.setAttribute('position', new BufferAttribute(positions, 3));
        return geometry;
    }, []);

    // Calculate positions for cameras in a grid
    const cameraPositions = useMemo(() => {
        const numCameras = connectedCameraIds.length;
        if (numCameras === 0) return [];

        const maxRowsColumns = Math.ceil(Math.sqrt(numCameras));
        const verticalSpacing = 2.5;
        const horizontalSpacing = 2.2;
        const verticalOffset = 1;

        return connectedCameraIds.map((_, index) => {
            const columnIndex = index % maxRowsColumns;
            const rowIndex = Math.floor(index / maxRowsColumns);

            const xPosition = columnIndex * horizontalSpacing - (maxRowsColumns * horizontalSpacing) / 2;
            const yPosition = rowIndex * verticalSpacing + verticalOffset;
            const zPosition = 0;

            return [xPosition, yPosition, zPosition] as [number, number, number];
        });
    }, [connectedCameraIds]);

    // Helper function to calculate virtual points
    const calculateVirtualPoint = (points: Map<string, Point3d>, virtualName: string): Point3d | null => {
        switch(virtualName) {
            case "head_center": {
                const leftEar = points.get("body.left_ear");
                const rightEar = points.get("body.right_ear");
                if (!leftEar || !rightEar) return null;
                return {
                    x: (leftEar.x + rightEar.x) / 2,
                    y: (leftEar.y + rightEar.y) / 2,
                    z: (leftEar.z + rightEar.z) / 2
                };
            }
            case "neck_center": {
                const leftShoulder = points.get("body.left_shoulder");
                const rightShoulder = points.get("body.right_shoulder");
                if (!leftShoulder || !rightShoulder) return null;
                return {
                    x: (leftShoulder.x + rightShoulder.x) / 2,
                    y: (leftShoulder.y + rightShoulder.y) / 2,
                    z: (leftShoulder.z + rightShoulder.z) / 2
                };
            }
            case "hips_center": {
                const leftHip = points.get("body.left_hip");
                const rightHip = points.get("body.right_hip");
                if (!leftHip || !rightHip) return null;
                return {
                    x: (leftHip.x + rightHip.x) / 2,
                    y: (leftHip.y + rightHip.y) / 2,
                    z: (leftHip.z + rightHip.z) / 2
                };
            }
            default:
                return points.get(virtualName) || null;
        }
    };

    // Subscribe to tracked points updates
    useEffect(() => {
        const unsubscribe = subscribeToTrackedPoints((newPoints: Map<string, Point3d>) => {
            // Only update the ref and mark dirty indices - no React state updates!
            const prevPoints = trackedPointsRef.current;
            trackedPointsRef.current = newPoints;
            needsLineUpdate.current = true; // Mark lines for update

            // Find new points that need indices assigned
            for (const [pointName, point] of newPoints) {
                if (!pointNameToIndexRef.current.has(pointName)) {
                    // New point detected - assign it an index
                    if (nextAvailableIndexRef.current >= MAX_POINTS) {
                        console.error(`Maximum points (${MAX_POINTS}) exceeded!`);
                        continue;
                    }
                    const newIndex = nextAvailableIndexRef.current++;
                    pointNameToIndexRef.current.set(pointName, newIndex);
                    dirtyIndicesRef.current.add(newIndex);
                } else {
                    // Existing point - check if position changed
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

            // Mark removed points as dirty (move them far away to hide)
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

    // Initialize instance matrices on mount
    useEffect(() => {
        if (!instancedMeshRef.current) return;

        // Hide all instances initially by moving them far away
        const farAway = new Vector3(10000, 10000, 10000);
        for (let i = 0; i < MAX_POINTS; i++) {
            DUMMY.position.copy(farAway);
            DUMMY.scale.set(POINT_SCALE, POINT_SCALE, POINT_SCALE);
            DUMMY.updateMatrix();
            instancedMeshRef.current.setMatrixAt(i, DUMMY.matrix);
        }
        instancedMeshRef.current.instanceMatrix.needsUpdate = true;
        instancedMeshRef.current.count = MAX_POINTS;
    }, []);

    // Update matrices in the render loop for maximum performance
    useFrame(() => {
        // Update camera orientations
        cameraRefs.current.forEach(camera => {
            if (camera) {
                camera.lookAt(0, 0, 0);
            }
        });

        const scale = 1 // Adjust this to fit your scene
        const farAway = new Vector3(10000, 10000, 10000);

        // Update points if we have dirty indices
        if (instancedMeshRef.current && dirtyIndicesRef.current.size > 0) {
            const mesh = instancedMeshRef.current;
            const points = trackedPointsRef.current;
            const nameToIndex = pointNameToIndexRef.current;

            // Process only dirty indices
            for (const index of dirtyIndicesRef.current) {
                // Find the point name for this index
                let pointName: string | null = null;
                for (const [name, idx] of nameToIndex) {
                    if (idx === index) {
                        pointName = name;
                        break;
                    }
                }

                if (pointName && points.has(pointName)) {
                    // Update position for visible point
                    const point = points.get(pointName)!;
                    DUMMY.position.set(
                        point.x * scale,
                        point.y * scale,
                        (point.z - 15) * scale  // Center around z=15 then scale
                    );
                    DUMMY.scale.set(POINT_SCALE, POINT_SCALE, POINT_SCALE);
                } else {
                    // Hide removed/missing points
                    DUMMY.position.copy(farAway);
                    DUMMY.scale.set(0, 0, 0);
                }

                DUMMY.updateMatrix();
                mesh.setMatrixAt(index, DUMMY.matrix);
            }

            // Only update the GPU buffer if we made changes
            if (dirtyIndicesRef.current.size > 0) {
                mesh.instanceMatrix.needsUpdate = true;
                dirtyIndicesRef.current.clear();
            }
        }

        // Update line segments
        if (lineSegmentsRef.current && needsLineUpdate.current) {
            const points = trackedPointsRef.current;
            const positions = lineGeometry.attributes.position.array as Float32Array;
            let segmentIndex = 0;

            for (const [segmentName, segment] of Object.entries(SEGMENT_DEFINITIONS)) {
                const proximalPoint = calculateVirtualPoint(points, segment.proximal);
                const distalPoint = calculateVirtualPoint(points, segment.distal);

                if (proximalPoint && distalPoint) {
                    // Set proximal vertex
                    positions[segmentIndex * 6] = proximalPoint.x * scale;
                    positions[segmentIndex * 6 + 1] = proximalPoint.y * scale;
                    positions[segmentIndex * 6 + 2] = (proximalPoint.z - 15) * scale;

                    // Set distal vertex
                    positions[segmentIndex * 6 + 3] = distalPoint.x * scale;
                    positions[segmentIndex * 6 + 4] = distalPoint.y * scale;
                    positions[segmentIndex * 6 + 5] = (distalPoint.z - 15) * scale;
                } else {
                    // Hide segment if points not available
                    for (let i = 0; i < 6; i++) {
                        positions[segmentIndex * 6 + i] = 10000;
                    }
                }

                segmentIndex++;
            }

            lineGeometry.attributes.position.needsUpdate = true;
            needsLineUpdate.current = false;
        }
    });

    return (
        <>
            <CameraControls makeDefault/>

            <ambientLight intensity={0.5}/>
            <directionalLight
                castShadow
                position={[5, 5, 5]}
                intensity={0.5}
                shadow-mapSize={1024}
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

            {/* Single InstancedMesh for all tracked points */}
            <instancedMesh
                ref={instancedMeshRef}
                args={[sphereGeometry, sphereMaterial, MAX_POINTS]}
                frustumCulled={false}
            />

            {/* Line segments for body connections */}
            <lineSegments
                ref={lineSegmentsRef}
                geometry={lineGeometry}
                material={lineMaterial}
                frustumCulled={false}
            />
        </>
    );
}