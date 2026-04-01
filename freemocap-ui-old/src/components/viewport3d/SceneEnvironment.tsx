import { Grid } from "@react-three/drei";

/** Static scene environment: lighting, ground grid, and axes indicator. */
export function SceneEnvironment() {
    return (
        <>
            <ambientLight intensity={0.6} />
            <directionalLight
                castShadow
                position={[5, 5, 5]}
                intensity={0.5}
                shadow-mapSize={1024}
            />
            {/* Fill light from below to prevent pure-black undersides */}
            <directionalLight
                position={[-3, -2, -3]}
                intensity={0.15}
            />

            <Grid
                renderOrder={-1}
                position={[0, -0.01, 0]}
                infiniteGrid
                cellSize={1}
                cellThickness={0.5}
                sectionSize={3}
                sectionThickness={1}
                //@ts-ignore — drei Grid typing doesn't expose sectionColor as tuple
                sectionColor={[0.25, 0, 0.25]}
                fadeDistance={100}
            />

            <axesHelper />
        </>
    );
}
