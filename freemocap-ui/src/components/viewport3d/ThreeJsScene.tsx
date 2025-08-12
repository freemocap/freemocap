import {useMemo, useRef} from "react";
import {CameraHelper, InstancedMesh, Matrix4, MeshStandardMaterial, PerspectiveCamera, SphereGeometry} from "three";
import {extend, useFrame} from "@react-three/fiber";
import {CameraControls, Grid} from "@react-three/drei";
import {ImageMesh} from "@/components/viewport3d/ImageMesh";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

extend({CameraHelper});

export function ThreeJsScene() {
    const {latestCameraData} = useWebSocketContext();
    const sphereRef = useRef<InstancedMesh>(null);
    const cameraRefs = useRef<PerspectiveCamera[]>([]);
    const latestPoints3d = {} // dummy for now
    const numPoints = Object.keys(latestPoints3d).length;

    const sphereGeometry = useMemo(() => new SphereGeometry(0.1, 16, 16), []);
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({color: 'red'}), []);

    const cameraPositions = [
        [3, 1, 3],
        [-3, 1, 3],
        [3, 1, -3],
        [-3, 1, -3],
    ]
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
            {cameraPositions.map((position, index) => (
                <perspectiveCamera
                    key={index}
                    ref={el => cameraRefs.current[index] = el!}
                    // @ts-ignore
                    position={position}
                    near={0.1}
                    far={1}
                />
            ))}
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
            {latestCameraData &&
                Object.entries(latestCameraData).map(([cameraId, cameraImageData], index) =>
                    cameraImageData?.imageBitmap ? (
                        <ImageMesh
                            key={cameraId}
                            cameraImageData={cameraImageData}
                            position={[index * 2.5, 1, 0]}
                        />
                    ) : null
                )}
            {numPoints > 0 && (
                <instancedMesh ref={sphereRef} args={[sphereGeometry, sphereMaterial, numPoints]}/>
            )}
        </>
    );
}
