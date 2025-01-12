import {Canvas} from "@react-three/fiber";
import {CameraControls, Grid} from "@react-three/drei";
import {Axes3dArrows} from "@/components/viewport3d/Axes3dArrows";
import {useWebSocketContext} from "@/context/WebSocketContext";
import {ImageMesh} from "@/components/viewport3d/ImageMesh";
import {useEffect, useRef} from "react";
import {InstancedMesh, Matrix4, MeshStandardMaterial, SphereGeometry} from "three";

export function ThreeJSCanvas3d() {
    const {latestImages, latestPoints3d} = useWebSocketContext();
    const sphereRef = useRef<InstancedMesh>(null);
    const numPoints = Object.keys(latestPoints3d || {}).length

    useEffect(() => {
        if (sphereRef.current) {
            let index = 0;
            Object.entries(latestPoints3d || {}).forEach(([key, [x, y, z]]) => {
                const matrix = new Matrix4();
                matrix.setPosition(x, y, z);
                sphereRef.current?.setMatrixAt(index, matrix);
                index++
            });
            sphereRef.current.instanceMatrix.needsUpdate = true;
        }
    }, [latestPoints3d]);

    return (
        <div className="h-screen w-screen">
            <Canvas shadows camera={{position: [5, 5, 5], fov: 75}}>
                <CameraControls makeDefault/>
                {/*<Environment preset="studio" />*/}
                <ambientLight intensity={0.1}/>
                <directionalLight
                    castShadow
                    position={[0, 0.01, 0]}
                    intensity={.1}
                    shadow-mapSize={1024}
                />
                <Grid
                    renderOrder={-1}
                    position={[0, -.01, 0]}
                    infiniteGrid
                    cellSize={1}
                    cellThickness={0.5}
                    sectionSize={3}
                    sectionThickness={1}
                    // @ts-ignore
                    sectionColor={[0.5, 0., 0.5]}
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
                    <instancedMesh ref={sphereRef}
                                   args={[new SphereGeometry(0.1, 16, 16),
                                       new MeshStandardMaterial({color: 'red'}), numPoints]}/>
                )}
            </Canvas>
        </div>
    );
}
