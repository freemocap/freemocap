import {Canvas} from "@react-three/fiber";
import {ThreeJsScene} from "@/components/viewport3d/ThreeJsScene";
import * as THREE from "three";
import {useEffect, useRef} from "react";


let renderer: THREE.WebGLRenderer | null = null;

function getRenderer() {
    if (!renderer) {
        renderer = new THREE.WebGLRenderer({antialias: true});
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);
    }
    return renderer;
}

export function ThreeJsCanvas() {
    // const canvasRef = useRef(null);
    // useEffect(() => {
    //     const currentRenderer = getRenderer();
    //     return () => {
    //         // Optionally, you can detach the renderer on unmount
    //         // currentRenderer.dispose();
    //     };
    // }, []);

    return (
        // <div className="h-screen w-screen" ref={canvasRef}>
        <div className="h-screen w-screen" >
            <Canvas
                shadows
                camera={{position: [5, 5, 5], fov: 75}}
                // gl={getRenderer()}
            >
                <ThreeJsScene/>
            </Canvas>
        </div>
    );
}



