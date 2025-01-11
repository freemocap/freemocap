import {Canvas} from "@react-three/fiber";
import {CameraControls, Environment, Grid} from "@react-three/drei";
import {Axes3dArrows} from "@/components/viewport3d/Axes3dArrows";

export function Viewport3d() {
    return (
        <div className="h-1/4 w=1/4">
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

            </Canvas>
        </div>
    );
}
