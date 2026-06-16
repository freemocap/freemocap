import { useEffect, useMemo, useRef } from "react";
import {
    Color,
    InstancedMesh,
    MeshBasicMaterial,
    Object3D,
    SphereGeometry,
    Vector3,
} from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { useWorkerData } from "../WorkerDataContext";
import { useViewportState } from "../scene/ViewportStateContext";
import { COLORS } from "../helpers/colors";
import { classifyPointName, getPointStyle } from "../helpers/skeleton-config";
import { useKeypointsSource, type KeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";

const MAX_POINTS = 1024;
const DUMMY = new Object3D();
const FAR_AWAY = new Vector3(1e5, 1e5, 1e5);

// ---------------------------------------------------------------------------
// Per‑category keypoint radii.
//
// The sphere geometry has radius 50, so the visual world‑space radius is
// roughly <constant> × 50.  Tweak these to taste — the filtered (colored‑by‑
// body‑part) layer uses the per‑category values, while the raw layer uses
// RAW_KEYPOINT_RADIUS uniformly.
// ---------------------------------------------------------------------------
const RAW_KEYPOINT_RADIUS = 0.07;

const BODY_KEYPOINT_RADIUS = 0.12;
const HAND_KEYPOINT_RADIUS = 0.05;
const FACE_KEYPOINT_RADIUS = 0.02;
const UNSPECIFIED_KEYPOINT_RADIUS = 0.1;

function getKeypointRadius(name: string): number {
    switch (classifyPointName(name)) {
        case "face":        return FACE_KEYPOINT_RADIUS;
        case "left_hand":
        case "right_hand":  return HAND_KEYPOINT_RADIUS;
        case "left":
        case "right":
        case "center":      return BODY_KEYPOINT_RADIUS;
        default:            return UNSPECIFIED_KEYPOINT_RADIUS;
    }
}

// ---------------------------------------------------------------------------
// KeypointLayer — one instanced‑mesh pass (raw or filtered).
// ---------------------------------------------------------------------------
interface KeypointLayerProps {
    subscribeKey: "subscribeToKeypointsRaw" | "subscribeToKeypointsFiltered";
    color: Color;
    radius: number;
    statsKey: "keypointsRaw" | "keypointsFiltered";
    colorMode?: "uniform" | "byBodyPart";
}

function KeypointLayer({ subscribeKey, color, radius, statsKey, colorMode = "uniform" }: KeypointLayerProps) {
    const workerData = useWorkerData();
    const keypointsSource: KeypointsSource = useKeypointsSource();
    const { statsRef } = useViewportState();
    const { invalidate } = useThree();
    const meshRef = useRef<InstancedMesh>(null);
    const frameRef = useRef<KeypointsFrame | null>(null);
    const dirtyRef = useRef(false);
    const nameToInstanceIdx = useRef<Map<string, number>>(new Map());
    const frameIdxByName = useRef<Map<string, number>>(new Map());
    const lastPointNamesRef = useRef<readonly string[] | null>(null);
    const nextIdx = useRef(0);

    // Low-poly sphere (6×4 = 24 tris vs 8×6 = 48). MeshBasicMaterial skips all
    // lighting calculations — significant savings at 1024 instanced meshes.
    const geo = useMemo(() => new SphereGeometry(50, 6, 4), []);
    const mat = useMemo(() => new MeshBasicMaterial({ color: "#ffffff" }), []);

    useEffect(() => () => { geo.dispose(); mat.dispose(); }, [geo, mat]);

    // Pull color hints from the active schema (if any) so per-name palette
    // overrides from the YAML propagate into the 3D view.
    const rawColorHints = useMemo(() => {
        const schema = workerData.getActiveSchema();
        return schema?.color_hints;
    }, [workerData, workerData.activeTrackerId, workerData.trackerSchemas]);

    // Pre-build Color objects so getPointStyle doesn't allocate inside useFrame.
    const colorHints = useMemo((): Record<string, Color> | undefined => {
        if (!rawColorHints) return undefined;
        return Object.fromEntries(
            Object.entries(rawColorHints).map(([name, hex]) => [name, new Color(hex)])
        ) as Record<string, Color>;
    }, [rawColorHints]);

    useEffect(() => {
        const subscribeFn = keypointsSource[subscribeKey];
        return subscribeFn((frame: KeypointsFrame) => {
            frameRef.current = frame;
            dirtyRef.current = true;
            invalidate();

            // Only rebuild index maps when the point-name list changes (e.g. on schema switch).
            if (frame.pointNames !== lastPointNamesRef.current) {
                lastPointNamesRef.current = frame.pointNames;
                frameIdxByName.current.clear();
                for (let i = 0; i < frame.pointNames.length; i++) {
                    const name = frame.pointNames[i];
                    frameIdxByName.current.set(name, i);
                    if (!nameToInstanceIdx.current.has(name)
                        && nextIdx.current < MAX_POINTS
                        && classifyPointName(name) !== 'face') {
                        nameToInstanceIdx.current.set(name, nextIdx.current++);
                    }
                }
            }
        });
    }, [keypointsSource, subscribeKey, invalidate]);

    useEffect(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        for (let i = 0; i < MAX_POINTS; i++) {
            DUMMY.position.copy(FAR_AWAY);
            DUMMY.scale.set(0, 0, 0);
            DUMMY.updateMatrix();
            mesh.setMatrixAt(i, DUMMY.matrix);
            mesh.setColorAt(i, COLORS.hidden);
        }
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        mesh.count = MAX_POINTS;
    }, []);

    useFrame(() => {
        const mesh = meshRef.current;
        if (!mesh || !dirtyRef.current) return;
        const t0 = performance.now();
        const frame = frameRef.current;
        const interleaved = frame?.interleaved;
        let count = 0;

        for (const [name, instanceIdx] of nameToInstanceIdx.current) {
            const frameIdx = interleaved ? frameIdxByName.current.get(name) : undefined;
            let visible = false;
            let x = 0, y = 0, z = 0;

            if (frameIdx !== undefined && interleaved) {
                const off = frameIdx * 4;
                const vis = interleaved[off + 3];
                x = interleaved[off];
                y = interleaved[off + 1];
                z = interleaved[off + 2];
                visible = vis > 0 && Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z);
            }

            if (visible) {
                const scale = colorMode === "byBodyPart"
                    ? getKeypointRadius(name)
                    : radius;
                const pointColor = colorMode === "byBodyPart"
                    ? getPointStyle(name, colorHints).color
                    : color;

                DUMMY.position.set(x, y, z);
                DUMMY.scale.setScalar(scale);
                mesh.setColorAt(instanceIdx, pointColor);
                count++;
            } else {
                DUMMY.position.copy(FAR_AWAY);
                DUMMY.scale.set(0, 0, 0);
                mesh.setColorAt(instanceIdx, COLORS.hidden);
            }
            DUMMY.updateMatrix();
            mesh.setMatrixAt(instanceIdx, DUMMY.matrix);
        }

        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        dirtyRef.current = false;
        statsRef.current[statsKey] = count;
        const elapsed = performance.now() - t0;
        if (elapsed > 8) console.warn(`KeypointLayer (${statsKey}) useFrame: ${elapsed.toFixed(1)}ms`);
    });

    return (
        <instancedMesh ref={meshRef} args={[geo, mat, MAX_POINTS]} frustumCulled={false} />
    );
}

export function KeypointsRenderer() {
    const { visibility } = useViewportState();

    return (
        <>
            {visibility.keypointsRaw && (
                <KeypointLayer
                    subscribeKey="subscribeToKeypointsRaw"
                    color={COLORS.raw}
                    radius={RAW_KEYPOINT_RADIUS}
                    statsKey="keypointsRaw"
                />
            )}
            {visibility.keypointsFiltered && (
                <KeypointLayer
                    subscribeKey="subscribeToKeypointsFiltered"
                    color={COLORS.filtered}
                    radius={RAW_KEYPOINT_RADIUS}
                    statsKey="keypointsFiltered"
                    colorMode="byBodyPart"
                />
            )}
        </>
    );
}
