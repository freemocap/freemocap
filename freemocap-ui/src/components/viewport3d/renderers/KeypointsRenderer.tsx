import { useEffect, useMemo, useRef, useState } from "react";
import {
    Color,
    InstancedMesh,
    MeshBasicMaterial,
    Object3D,
    SphereGeometry,
} from "three";
import { useFrame, useThree } from "@react-three/fiber";
import type { ModelDefinition } from "@/services/server/transport/message-contract";
import { useViewportState } from "../scene/ViewportStateContext";
import { COLORS } from "../helpers/colors";
import { classifyPointName, getPointStyle } from "../helpers/skeleton-config";
import { registerPickingMesh, unregisterPickingMesh } from "./PickingRegistry";
import { useKeypointsSource, type KeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";

const MAX_POINTS = 1024;
const DUMMY = new Object3D();

// ---------------------------------------------------------------------------
// Per‑category keypoint radii.
//
// The sphere geometry has radius 50, so the visual world‑space radius is
// roughly <constant> × 50.  Tweak these to taste — the filtered (colored‑by‑
// body‑part) layer uses the per‑category values, while the raw layer uses
// RAW_KEYPOINT_RADIUS uniformly.
// ---------------------------------------------------------------------------
const RAW_KEYPOINT_RADIUS = 0.12;
const SKELETON_POINT_RADIUS = 0.15;

const BODY_KEYPOINT_RADIUS = 0.18;
const HAND_KEYPOINT_RADIUS = 0.09;
const FACE_KEYPOINT_RADIUS = 0.06;
const UNSPECIFIED_KEYPOINT_RADIUS = 0.15;

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

/**
 * Content-equality for point-name lists. The worker boundary structured-clones
 * each frame, so `frame.pointNames` is a fresh array reference every frame even
 * when the names are unchanged — a reference check would rebuild the index maps
 * every frame. Comparing by content fires the rebuild only on a real schema /
 * keypoint-set change.
 */
function samePointNames(a: readonly string[], b: readonly string[] | null): boolean {
    if (b === null || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
}

// ---------------------------------------------------------------------------
// KeypointLayer — one instanced‑mesh pass (raw or filtered).
// ---------------------------------------------------------------------------
interface KeypointLayerProps {
    /** Which points this layer draws: the raw triangulated measurements from every
     *  detector, or every tracked model's fitted LANDMARKS. The second is what shows a
     *  charuco board as a reconstructed rigid object rather than a cloud of corners. */
    pointSource: "keypoints" | "modelLandmarks";
    color: Color;
    radius: number;
    statsKey: "keypoints" | "skeleton";
    colorMode?: "uniform" | "byBodyPart";
    /** Values per point in the interleaved frame data. Every PointsFrame is
     *  3-interleaved xyz: frame-resolution strips the 4th column
     *  (reprojection_error) from KEYPOINTS_3D and SEGMENT_ORIGINS is natively
     *  3-column. */
    stride: 3 | 4;
    /** The inspection kind reported when this layer's points are hovered/clicked. */
    inspectionKind: "keypoint" | "landmark";
}

function KeypointLayer({ pointSource, color, radius, statsKey, colorMode = "uniform", stride, inspectionKind }: KeypointLayerProps) {
    const keypointsSource: KeypointsSource = useKeypointsSource();
    const { statsRef } = useViewportState();
    const { invalidate } = useThree();
    const meshRef = useRef<InstancedMesh>(null);
    const frameRef = useRef<KeypointsFrame | null>(null);
    const dirtyRef = useRef(false);
    const nameToInstanceIdx = useRef<Map<string, number>>(new Map());
    const instanceIdxToName = useRef<Map<number, string>>(new Map());
    const frameIdxByName = useRef<Map<string, number>>(new Map());
    const lastPointNamesRef = useRef<readonly string[] | null>(null);
    const nextIdx = useRef(0);

    // Ultra-low-poly sphere (4×3 = 12 tris). At the tiny rendered size
    // (radius 0.02–0.12 world units) this is visually identical to 6×4.
    // MeshBasicMaterial skips all lighting calculations.
    const geo = useMemo(() => new SphereGeometry(50, 4, 3), []);
    const mat = useMemo(() => new MeshBasicMaterial({ color: "#ffffff" }), []);

    useEffect(() => () => { geo.dispose(); mat.dispose(); }, [geo, mat]);

    // Per-name colors declared by the MODEL: every landmark group carries its tags'
    // resolved color, so a board's charuco corners come out green and its aruco corners
    // orange because the model said so — not because a renderer matched their names.
    // Rebuilt whenever the model set changes.
    const [colorHints, setColorHints] = useState<Record<string, Color> | undefined>(undefined);
    const hintSignatureRef = useRef<string>("");

    useEffect(() => {
        if (pointSource !== "modelLandmarks") return;
        // Driven by the STATIC model channel, so this fires when the model set changes and
        // not once per frame.
        const rebuildHints = (models: ModelDefinition[]): void => {
            const signature = models.map((m) => `${m.model_id}:${m.landmark_groups.length}`).join("|");
            if (signature === hintSignatureRef.current) return;
            hintSignatureRef.current = signature;
            const hints: Record<string, Color> = {};
            for (const model of models) {
                for (const group of model.landmark_groups) {
                    const groupColor = new Color(group.color);
                    for (const name of group.landmark_names) hints[name] = groupColor;
                }
            }
            setColorHints(Object.keys(hints).length > 0 ? hints : undefined);
        };
        const existing = keypointsSource.getModels();
        if (existing) rebuildHints(existing);
        return keypointsSource.subscribeToModels(rebuildHints);
    }, [keypointsSource, pointSource]);

    useEffect(() => {
        const handleFrame = (frame: KeypointsFrame) => {
            frameRef.current = frame;
            dirtyRef.current = true;
            invalidate();

            // Only rebuild index maps when the point-name list changes (e.g. on model switch).
            // Content comparison, not reference: the worker boundary clones each frame.
            if (!samePointNames(frame.pointNames, lastPointNamesRef.current)) {
                lastPointNamesRef.current = frame.pointNames;
                frameIdxByName.current.clear();
                for (let i = 0; i < frame.pointNames.length; i++) {
                    const name = frame.pointNames[i];
                    frameIdxByName.current.set(name, i);
                    if (!nameToInstanceIdx.current.has(name)
                        && nextIdx.current < MAX_POINTS
                        && classifyPointName(name) !== 'face') {
                        const idx = nextIdx.current++;
                        nameToInstanceIdx.current.set(name, idx);
                        instanceIdxToName.current.set(idx, name);
                    }
                }
            }
        };

        if (pointSource === "keypoints") {
            return keypointsSource.subscribeToKeypoints(handleFrame);
        }
        // Every model's landmarks in one cloud. Concatenated rather than "the first
        // model's", because a frame carries several tracked things and their name spaces
        // are disjoint — showing only one of them was the single-object assumption.
        return keypointsSource.subscribeToModelFrames((models) => {
            const names: string[] = [];
            let total = 0;
            for (const entry of models) {
                if (!entry.landmarks) continue;
                names.push(...entry.landmarks.names);
                total += entry.landmarks.data.length;
            }
            if (names.length === 0) return;
            const interleaved = new Float32Array(total);
            let offset = 0;
            for (const entry of models) {
                if (!entry.landmarks) continue;
                interleaved.set(entry.landmarks.data, offset);
                offset += entry.landmarks.data.length;
            }
            handleFrame({ pointNames: names, interleaved });
        });
    }, [keypointsSource, pointSource, invalidate]);

    useEffect(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        for (let i = 0; i < MAX_POINTS; i++) {
            DUMMY.position.set(0, 0, 0);
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
                const off = frameIdx * stride;
                x = interleaved[off];
                y = interleaved[off + 1];
                z = interleaved[off + 2];
                // The data is displayed as received — no visibility gating: the
                // 4th value of a KEYPOINTS_3D point is reprojection_error, not
                // a confidence to filter on. NaN (missing) rows hide the point.
                visible = Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z);
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
                DUMMY.position.set(0, 0, 0);
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

    // Register this mesh with the manual raycast picker (the worker has no R3F
    // pointer event manager, so hover/click is done by ViewportPicker).
    useEffect(() => {
        const mesh = meshRef.current;
        if (!mesh) return;
        registerPickingMesh(mesh, { kind: inspectionKind, instanceIdToName: instanceIdxToName.current });
        return () => unregisterPickingMesh(mesh);
    }, [inspectionKind]);

    return (
        <instancedMesh
            ref={meshRef}
            args={[geo, mat, MAX_POINTS]}
            frustumCulled={false}
        />
    );
}

export function KeypointsRenderer() {
    const { visibility } = useViewportState();

    return (
        <>
            {visibility.keypoints && (
                <KeypointLayer
                    pointSource="keypoints"
                    color={COLORS.filtered}
                    radius={RAW_KEYPOINT_RADIUS}
                    statsKey="keypoints"
                    colorMode="byBodyPart"
                    stride={3}
                    inspectionKind="keypoint"
                />
            )}
            {visibility.skeleton && (
                <KeypointLayer
                    pointSource="modelLandmarks"
                    color={COLORS.skeleton}
                    radius={SKELETON_POINT_RADIUS}
                    statsKey="skeleton"
                    colorMode="byBodyPart"
                    stride={3}
                    inspectionKind="landmark"
                />
            )}
        </>
    );
}
