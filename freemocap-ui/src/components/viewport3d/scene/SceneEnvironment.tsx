import { Grid } from "@react-three/drei";
import { useViewportState } from "./ViewportStateContext";

export function SceneEnvironment() {
    const { visibility } = useViewportState();
    if (!visibility.environment) return null;

    return (
        <>
            <ambientLight intensity={0.6} />
            <directionalLight position={[3e3, 3e3, 3e3]} intensity={0.5} />
            <directionalLight position={[-3e3, -2e3, -3e3]} intensity={0.3} />
            <Grid
                renderOrder={-1}
                position={[0, -0.01, 0]}
                infiniteGrid
                cellSize={1000}
                cellThickness={0.5}
                sectionSize={50}
                sectionThickness={1}
                // @ts-ignore
                sectionColor={[0.1, 0, 0.1]}
                fadeDistance={10000}
            />
            <axesHelper scale={100} />
        </>
    );
}
