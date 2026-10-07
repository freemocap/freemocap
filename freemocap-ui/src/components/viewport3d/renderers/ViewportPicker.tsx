import { useEffect, useMemo, useRef } from "react";
import { useThree } from "@react-three/fiber";
import { InstancedMesh, Raycaster, Vector2 } from "three";
import { useViewportState } from "../scene/ViewportStateContext";
import type { InspectionKind } from "../helpers/viewport3d-types";
import { getPickingEntries } from "./PickingRegistry";

/** A press that travels further than this before release is a drag, not a click. */
const CLICK_MAX_TRAVEL_PX = 4;

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
    const pressRef = useRef<{ x: number; y: number } | null>(null);

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

        const onLeave = () => {
            if (lastHoverRef.current) {
                lastHoverRef.current = null;
                setHovered(null);
            }
        };

        // Pin on a click, not on every press: a press that turns into an orbit drag
        // must not pin whatever happened to be under the cursor when it started.
        const onDown = (e: Event) => {
            const { clientX, clientY } = e as unknown as { clientX: number; clientY: number };
            pressRef.current = { x: clientX, y: clientY };
        };
        const onUp = (e: Event) => {
            const press = pressRef.current;
            pressRef.current = null;
            if (!press) return;
            const { clientX, clientY } = e as unknown as { clientX: number; clientY: number };
            if (Math.hypot(clientX - press.x, clientY - press.y) > CLICK_MAX_TRAVEL_PX) return;
            const t = pick(clientX, clientY);
            if (t) setPinned(t);
        };

        canvas.addEventListener("pointermove", onMove);
        canvas.addEventListener("pointerleave", onLeave);
        canvas.addEventListener("pointerdown", onDown);
        canvas.addEventListener("pointerup", onUp);
        return () => {
            canvas.removeEventListener("pointermove", onMove);
            canvas.removeEventListener("pointerleave", onLeave);
            canvas.removeEventListener("pointerdown", onDown);
            canvas.removeEventListener("pointerup", onUp);
        };
    }, [camera, gl, size, raycaster, pointer, setHovered, setPinned]);

    return null;
}
