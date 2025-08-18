import {useMemo, useRef} from "react";
import {CameraHelper, InstancedMesh, Matrix4, MeshStandardMaterial, PerspectiveCamera, SphereGeometry} from "three";
import {extend, useFrame} from "@react-three/fiber";
import {CameraControls, Grid} from "@react-three/drei";
import {ImageMesh} from "@/components/viewport3d/ImageMesh";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

extend({CameraHelper});

export function ThreeJsScene() {
    const {latestImageData} = useWebSocketContext();
    const sphereRef = useRef<InstancedMesh>(null);
    const cameraRefs = useRef<PerspectiveCamera[]>([]);
    const latestPoints3d = {} // dummy for now
    const numPoints = latestPoints3d?Object.keys(latestPoints3d).length : 0;
    const numberOfCameras = latestImageData ? Object.keys(latestImageData).length : 0;
    const sphereGeometry = useMemo(() => new SphereGeometry(0.1, 16, 16), []);
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({color: 'red'}), []);
    const maxRowsColumns = Math.ceil(Math.sqrt(numberOfCameras))+1;

    const cameraPositionsMap = Object.fromEntries(
        Object.entries(latestImageData).map(([cameraId, cameraImageData]) => {
            // Calculate position in a grid with max columns based on sqrt of camera count
            const cameraIndex = cameraImageData?.cameraIndex ;
            const columnIndex = cameraImageData?.cameraIndex % maxRowsColumns;
            const rowIndex = Math.floor(cameraImageData?.cameraIndex / maxRowsColumns);

            // Set spacing between cameras
            const verticalSpacing = 2.5;
            const horizontalSpacing = 2.2;
            const verticalOffset = 1;

            const xPosition = columnIndex * horizontalSpacing - horizontalSpacing; // Center the grid
            const yPosition = rowIndex * verticalSpacing + verticalOffset;
            // const xPosition = cameraIndex * horizontalSpacing - numberOfCameras/2; // Center the grid
            // const yPosition = 2;//rowIndex * verticalSpacing + verticalOffset;
            const zPosition = 0;

            return [cameraId, [xPosition, yPosition, zPosition]];
        })
    );
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
            {/*{cameraPositions.map((position, index) => (*/}
            {/*    <perspectiveCamera*/}
            {/*        key={index}*/}
            {/*        ref={el => cameraRefs.current[index] = el!}*/}
            {/*        // @ts-ignore*/}
            {/*        position={position}*/}
            {/*        near={0.1}*/}
            {/*        far={1}*/}
            {/*    />*/}
            {/*))}*/}
            {cameraRefs.current.map((camera, index) => camera && (
                <cameraHelper key={index} args={[camera]} />
            ))}
            <ambientLight intensity={0.1}/>
            <directionalLight
                castShadow
                position={[0, 0.01, 0]}
                intensity={0.1}
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
            {latestImageData &&
                Object.entries(latestImageData).map(([cameraId, cameraImageData], index) =>
                    cameraImageData?.imageBitmap ? (
                        <ImageMesh
                            key={cameraId}
                            cameraImageData={cameraImageData}
                            position={cameraPositionsMap[cameraId] as [number, number, number] }
                        />
                    ) : null
                )}
            {numPoints > 0 && (
                <instancedMesh ref={sphereRef} args={[sphereGeometry, sphereMaterial, numPoints]}/>
            )}
        </>
    );
}
