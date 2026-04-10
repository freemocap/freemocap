import {Grid} from "@react-three/drei";


/** Static scene environment: lighting, ground grid, and axes indicator. */
export function SceneEnvironment() {
    return (
        <>
            <ambientLight intensity={0.6} />
            <directionalLight
                castShadow
                position={[3e3, 3e3, 3e3]}
                intensity={0.5}
                shadow-mapSize={1024}
            />
            {/* Fill light from below to prevent pure-black undersides */}
            <directionalLight
                position={[-3e3, -2e3, -3e3]}
                intensity={0.5}
            />

            <Grid
                renderOrder={-1}
                position={[0, -0.01, 0]}
                infiniteGrid
                cellSize={1000}
                cellThickness={0.5}
                sectionSize={50}
                sectionThickness={1}
                //@ts-ignore — drei Grid typing doesn't expose sectionColor as tuple
                sectionColor={[0.1, 0, 0.1]}
                fadeDistance={10000}
            />

            <axesHelper
                scale={100}
            />
        </>
    );
}
