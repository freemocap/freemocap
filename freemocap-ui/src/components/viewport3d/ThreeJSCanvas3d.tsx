import {Canvas} from "@react-three/fiber";
import {CameraControls, Environment, Grid} from "@react-three/drei";
import {Axes3dArrows} from "@/components/viewport3d/Axes3dArrows";
import {useWebSocketContext} from "@/context/WebSocketContext";
import {ImageMesh} from "@/components/viewport3d/ImageMesh";

export function ThreeJSCanvas3d() {
    const {latestFrontendPayload} = useWebSocketContext();

    return (
        <div className="h-screen w-screen" >
            <Canvas shadows camera={{position:[5,5,5], fov:75}}>
                <CameraControls makeDefault />
                <Environment preset="studio" />
                <ambientLight intensity={0.3} />
                <directionalLight
                castShadow
                position={[0,0.01, 0]}
                intensity={1.5}
                shadow-mapSize={1024}
                />
                <Grid
                    renderOrder={-1}
                    position={[0,-.01,0]}
                    infiniteGrid
                    cellSize={1}
                    cellThickness={0.5}
                    sectionSize={3}
                    sectionThickness={1}
                    // @ts-ignore
                    sectionColor={[0.5, 0.5, 0.5]}
                    fadeDistance={30}
                    />
                <Axes3dArrows />

                {latestFrontendPayload  && latestFrontendPayload.jpeg_images &&
                    Object.entries(latestFrontendPayload.jpeg_images).map(([cameraId, base64Image], index) =>(
                        base64Image ? (
                            <ImageMesh
                                key={cameraId}
                                imageUrl={`data:/image?jpeg;base64,${base64Image}`}
                                position={[index*2.5, 1, 0 ]}
                                />
                        ) : null
                    ))
                }

            </Canvas>
        </div>
    );
}
