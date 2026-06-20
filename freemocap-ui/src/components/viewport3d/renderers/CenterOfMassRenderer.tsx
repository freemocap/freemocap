import {useEffect, useMemo, useRef} from "react";
import {Mesh, SphereGeometry, MeshBasicMaterial} from "three";
import {useFrame} from "@react-three/fiber";
import {useServerOptional} from "@/services/server/server-context";
import type {Point3d} from "@/components/viewport3d";

// Effective radius = 50 × 0.50 = 25 world units — softball-sized,
// ~4× larger than body keypoints (50 × 0.12 = 6).
const COM_SCALE = 0.50;
const COM_COLOR = "#44ff44"; // bright green

/**
 * Renders a large sphere at the total-body center of mass position,
 * updated every frame from the live websocket CoM stream.
 */
export function CenterOfMassRenderer() {
    const server = useServerOptional();
    const meshRef = useRef<Mesh>(null);
    const comRef = useRef<Point3d | null>(null);

    const geo = useMemo(() => new SphereGeometry(50, 16, 12), []);
    const mat = useMemo(() => new MeshBasicMaterial({color: COM_COLOR}), []);

    useEffect(() => () => { geo.dispose(); mat.dispose(); }, [geo, mat]);

    useEffect(() => {
        if (!server) {
            console.warn("[CoM] No server context — renderer inactive");
            return;
        }
        console.log("[CoM] Subscribing to center_of_mass stream");
        let received = 0;
        return server.subscribeToCenterOfMass((point) => {
            received++;
            if (received <= 3 || received % 60 === 0) {
                console.log(`[CoM] frame #${received}: x=${point?.x?.toFixed(3)} y=${point?.y?.toFixed(3)} z=${point?.z?.toFixed(3)} point=${point ? 'yes' : 'null'}`);
            }
            comRef.current = point;
        });
    }, [server]);

    useFrame(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        const com = comRef.current;
        if (com) {
            mesh.position.set(com.x, com.y, com.z);
            mesh.scale.setScalar(COM_SCALE);
            mesh.visible = true;
        } else {
            mesh.visible = false;
        }
    });

    if (!server) return null;

    return (
        <mesh ref={meshRef} geometry={geo} material={mat} frustumCulled={false} />
    );
}
