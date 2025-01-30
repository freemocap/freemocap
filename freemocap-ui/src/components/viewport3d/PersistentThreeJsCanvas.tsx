
import * as THREE from 'three';
import {useEffect} from "react";
import {Canvas} from "@react-three/fiber";
import {ThreeJsScene} from "@/components/viewport3d/ThreeJsScene";
import ReactDOM from "react-dom";

let renderer: THREE.WebGLRenderer | null = null;
function getRenderer() {
    if (!renderer) {
        renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);
    }
    return renderer;
}

export const PersistentThreeJsCanvas: React.FC = () => {
    useEffect(() => {
        let portalRoot = document.getElementById('threejs-root');

        if (!portalRoot) {
            portalRoot = document.createElement('div');
            portalRoot.id = 'threejs-root';
            document.body.appendChild(portalRoot);
        }

        const renderer = getRenderer();

        //handle window resize
        const handleWindowResize = () => {
            renderer.setSize(window.innerWidth, window.innerHeight);
        };

        window.addEventListener('resize', handleWindowResize)

        return () => {
            window.removeEventListener('resize', handleWindowResize)
        };
    }, []);

    const portalRoot = document.getElementById('threejs-root');

    if (!portalRoot) return null;

    return ReactDOM.createPortal(
        <Canvas shadows camera={{position: [5,5,5], fov:75}}>
            <ThreeJsScene/>
        </Canvas>,
        portalRoot
    )
}
