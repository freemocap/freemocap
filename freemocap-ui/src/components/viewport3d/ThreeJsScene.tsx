import {useMemo, useRef} from "react";
import {CameraHelper, InstancedMesh, Matrix4, MeshStandardMaterial, PerspectiveCamera, SphereGeometry} from "three";
import {extend, useFrame} from "@react-three/fiber";
import {CameraControls, Grid} from "@react-three/drei";
import {ImageMesh} from "@/components/viewport3d/ImageMesh";
import {useServer} from "@/services";

extend({CameraHelper});

export function ThreeJsScene() {
    const { connectedCameraIds } = useServer();
    const sphereRef = useRef<InstancedMesh>(null);
    const cameraRefs = useRef<PerspectiveCamera[]>([]);
    const latestPoints3d = {} // dummy for now
    const numPoints = latestPoints3d ? Object.keys(latestPoints3d).length : 0;

    const sphereGeometry = useMemo(() => new SphereGeometry(0.1, 16, 16), []);
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({color: 'red'}), []);

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

    useFrame(() => {
        // Make the camera look at the origin (0, 0, 0)
        cameraRefs.current.forEach(camera => {
            if (camera) {
                camera.lookAt(0, 0, 0);
            }
        })
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

            {/* Render ImageMesh for each connected camera */}
            {connectedCameraIds.map((cameraId, index) => (
                <ImageMesh
                    key={cameraId}
                    cameraId={cameraId}
                    position={cameraPositions[index] || [0, 0, 0]}
                />
            ))}

            {numPoints > 0 && (
                <instancedMesh ref={sphereRef} args={[sphereGeometry, sphereMaterial, numPoints]}/>
            )}
        </>
    );
}