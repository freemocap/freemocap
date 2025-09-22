import {Canvas} from "@react-three/fiber";
import {ThreeJsScene} from "@/components/viewport3d/ThreeJsScene";


export function ThreeJsCanvas() {

    return (
        <div className="h-screen w-screen" >
            <Canvas
                shadows
                camera={{position: [5, 5, 5], fov: 75}}
            >
                <ThreeJsScene/>
            </Canvas>
        </div>
    );
}



