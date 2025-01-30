import {useWebSocketContext} from "@/context/WebSocketContext";
import {useMemo, useRef} from "react";
import {InstancedMesh, Matrix4, MeshStandardMaterial, SphereGeometry} from "three";
import {useFrame} from "@react-three/fiber";
import {CameraControls, Grid} from "@react-three/drei";
import {Axes3dArrows} from "@/components/viewport3d/Axes3dArrows";
import {ImageMesh} from "@/components/viewport3d/ImageMesh";

export function ThreeJsScene() {
    const {latestImages, latestPoints3d} = useWebSocketContext();
    const sphereRef = useRef<InstancedMesh>(null);
    const numPoints = Object.keys(latestPoints3d || {}).length;

    const sphereGeometry = useMemo(() => new SphereGeometry(0.1, 16, 16), []);
    const sphereMaterial = useMemo(() => new MeshStandardMaterial({color: 'red'}), []);

    useFrame(() => {
        if (sphereRef.current && latestPoints3d) {
            let index = 0;
            Object.entries(latestPoints3d).forEach(([key, point]) => {
                if (point && point.length === 3) {
                    const [x, y, z] = point;
                    if (x !== null && y !== null && z !== null) {
                        const matrix = new Matrix4();
                        matrix.setPosition(x, y, z);
                        sphereRef.current?.setMatrixAt(index, matrix);
                        index++;
                    }
                }
            });
            sphereRef.current.instanceMatrix.needsUpdate = true;
        }
    });

    return (
        <>
            <CameraControls makeDefault/>
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
                fadeDistance={20}
            />
            <Axes3dArrows/>
            {latestImages &&
                Object.entries(latestImages).map(([cameraId, base64Image], index) =>
                    base64Image ? (
                        <ImageMesh
                            key={cameraId}
                            imageUrl={`data:/image?jpeg;base64,${base64Image}`}
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
