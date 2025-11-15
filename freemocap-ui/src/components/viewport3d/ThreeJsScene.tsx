import {useEffect, useMemo, useRef} from "react";
import {
    CameraHelper,
    InstancedMesh,
    MeshStandardMaterial,
    PerspectiveCamera,
    SphereGeometry,
    Object3D,
    Matrix4,
    Vector3
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

export function ThreeJsScene() {
    const { connectedCameraIds, subscribeToTrackedPoints } = useServer();
    const instancedMeshRef = useRef<InstancedMesh>(null);
    const cameraRefs = useRef<PerspectiveCamera[]>([]);

    // Performance-critical: Direct refs to avoid React re-renders
    const trackedPointsRef = useRef<Map<string, Point3d>>(new Map());
    const pointNameToIndexRef = useRef<Map<string, number>>(new Map());
    const nextAvailableIndexRef = useRef<number>(0);
    const dirtyIndicesRef = useRef<Set<number>>(new Set());

    // Pre-create geometry and material once
    const sphereGeometry = useMemo(() => new SphereGeometry(0.05, 8, 6), []); // Bigger spheres
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({
        color: '#ff0066', // Brighter color for visibility
        roughness: 0.4,
        metalness: 0.6,
        emissive: '#ff0066',
        emissiveIntensity: 0.2
    }), []);

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

    // Subscribe to tracked points updates
    useEffect(() => {
        const unsubscribe = subscribeToTrackedPoints((newPoints: Map<string, Point3d>) => {
            // Only update the ref and mark dirty indices - no React state updates!
            const prevPoints = trackedPointsRef.current;
            trackedPointsRef.current = newPoints;

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

        // Only update if we have dirty indices
        if (!instancedMeshRef.current || dirtyIndicesRef.current.size === 0) return;

        const mesh = instancedMeshRef.current;
        const points = trackedPointsRef.current;
        const nameToIndex = pointNameToIndexRef.current;
        const farAway = new Vector3(10000, 10000, 10000);

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
                // Scale coordinates to bring them closer to origin
                const scale = 0.2; // Adjust this to fit your scene
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
    });

    return (
        <>
            <CameraControls makeDefault/>

            {cameraRefs.current.map((camera, index) => camera && (
                <cameraHelper key={index} args={[camera]} />
            ))}

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
                sectionColor={[0.5, 0, 0.5]}
                fadeDistance={100}
            />

            <axesHelper/>

            {/* Single InstancedMesh for all tracked points */}
            <instancedMesh
                ref={instancedMeshRef}
                args={[sphereGeometry, sphereMaterial, MAX_POINTS]}
                frustumCulled={false}
            />
        </>
    );
}
