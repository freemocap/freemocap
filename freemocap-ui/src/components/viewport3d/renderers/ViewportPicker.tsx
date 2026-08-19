import { useEffect, useMemo, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { InstancedMesh, Raycaster, Vector2 } from "three";
import { useViewportState } from "../scene/ViewportStateContext";
import type { InspectionKind } from "../helpers/viewport3d-types";
import { getPickingEntries } from "./PickingRegistry";

/**
 * Manual raycast picking: the worker's R3F root has no pointer event manager
 * (events: undefined), so this component listens on the canvas EventTarget and
 * raycasts the registered instanced meshes itself, forwarding hover/click into
 * the viewport state (which the worker then posts to the main thread).
 */
export function ViewportPicker() {
    const camera = useThree((s) => s.camera);
    const gl = useThree((s) => s.gl);
    const size = useThree((s) => s.size);
    const { setHovered, setPinned } = useViewportState();

    const raycaster = useMemo(() => new Raycaster(), []);
    const pointer = useMemo(() => new Vector2(), []);
    const lastHoverRef = useRef<{ kind: InspectionKind; name: string } | null>(null);

    useEffect(() => {
        const canvas = gl.domElement;

        const pick = (clientX: number, clientY: number): { kind: InspectionKind; name: string } | null => {
            if (!size.width || !size.height) return null;
            pointer.x = (clientX / size.width) * 2 - 1;
            pointer.y = -(clientY / size.height) * 2 + 1;
            camera.updateProjectionMatrix();
            camera.updateMatrixWorld();
            raycaster.setFromCamera(pointer, camera);

            const entries = getPickingEntries();
            const meshes = [...entries.keys()];
            for (const mesh of meshes) {
                // InstancedMesh.raycast culls against its lazily-cached bounding
                // sphere. three.js computes that sphere once from whatever the
                // instance matrices held at that moment, so it goes stale as the
                // points move and was also corrupted by hidden instances flung to
                // (1e5,1e5,1e5). Recompute from the live matrices so the culling
                // sphere actually contains the points we can hit.
                mesh.computeBoundingSphere();
            }
            const hits = raycaster.intersectObjects(meshes, false);
            for (const hit of hits) {
                const entry = entries.get(hit.object as InstancedMesh);
                if (!entry) continue;
                const name = entry.instanceIdToName.get(hit.instanceId ?? -1);
                if (name) return { kind: entry.kind, name };
            }
            return null;
        };

        const onMove = (e: Event) => {
            const { clientX, clientY } = e as unknown as { clientX: number; clientY: number };
            const t = pick(clientX, clientY);
            if (t) {
                if (!lastHoverRef.current || lastHoverRef.current.kind !== t.kind || lastHoverRef.current.name !== t.name) {
                    lastHoverRef.current = t;
                    setHovered(t);
                }
            } else if (lastHoverRef.current) {
                lastHoverRef.current = null;
                setHovered(null);
            }
        };

        const onDown = (e: Event) => {
            const { clientX, clientY } = e as unknown as { clientX: number; clientY: number };
            const t = pick(clientX, clientY);
            if (t) setPinned(t);
        };

        canvas.addEventListener("pointermove", onMove);
        canvas.addEventListener("pointerdown", onDown);
        return () => {
            canvas.removeEventListener("pointermove", onMove);
            canvas.removeEventListener("pointerdown", onDown);
        };
    }, [camera, gl, size, raycaster, pointer, setHovered, setPinned]);

    return null;
}
