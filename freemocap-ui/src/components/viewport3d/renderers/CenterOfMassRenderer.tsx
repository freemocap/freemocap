import {useEffect, useMemo, useRef} from "react";
import {Mesh, SphereGeometry, MeshBasicMaterial} from "three";
import {useFrame, useThree} from "@react-three/fiber";
import {useViewportState} from "@/components/viewport3d/scene/ViewportStateContext";
import {workerDataStore} from "@/components/viewport3d/WorkerDataStore";
import type {Point3d} from "@/components/viewport3d";

// Effective radius = 50 × 0.50 = 25 world units — softball-sized,
// ~4× larger than body keypoints (50 × 0.12 = 6).
const COM_SCALE = 0.50;
const COM_COLOR = "#44ff44"; // bright green

/**
 * Renders a large sphere at the total-body center of mass position,
 * updated every frame from the live websocket CoM stream (routed
 * through the worker data store by CenterOfMassForwarder).
 */
export function CenterOfMassRenderer() {
    const { statsRef } = useViewportState();
    const invalidate = useThree(state => state.invalidate);
    const meshRef = useRef<Mesh>(null);
    const comRef = useRef<Point3d | null>(null);

    const geo = useMemo(() => new SphereGeometry(50, 16, 12), []);
    const mat = useMemo(() => new MeshBasicMaterial({color: COM_COLOR}), []);

    useEffect(() => () => { geo.dispose(); mat.dispose(); }, [geo, mat]);

    useEffect(() => {
        console.log("[CoM] Subscribing to center_of_mass stream (worker)");
        let received = 0;
        return workerDataStore.subscribeToCenterOfMass((point) => {
            received++;
            if (received <= 3 || received % 60 === 0) {
                console.log(`[CoM] frame #${received}: x=${point?.x?.toFixed(3)} y=${point?.y?.toFixed(3)} z=${point?.z?.toFixed(3)} point=${point ? 'yes' : 'null'}`);
            }
            comRef.current = point;
            invalidate();
        });
    }, [invalidate]);

    useFrame(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        const com = comRef.current;
        if (com) {
            mesh.position.set(com.x, com.y, com.z);
            mesh.scale.setScalar(COM_SCALE);
            mesh.visible = true;
            statsRef.current.centerOfMass = 1;
        } else {
            mesh.visible = false;
            statsRef.current.centerOfMass = 0;
        }
    });

    return (
        <mesh ref={meshRef} geometry={geo} material={mat} frustumCulled={false} />
    );
}
