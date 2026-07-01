import { useEffect, useMemo, useRef, useState } from "react";
import { InterleavedBufferAttribute, Vector2 } from "three";
import { useFrame, useThree } from "@react-three/fiber";
import {
    LineSegments2,
    LineSegmentsGeometry,
    LineMaterial,
} from "three-stdlib";
import { useWorkerData } from "../WorkerDataContext";
import { Point3d } from "../helpers/viewport3d-types";
import { useKeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";
import { useViewportState } from "../scene/ViewportStateContext";
import {
    buildSegmentsFromSchema,
    classifyPointName,
    MAX_SEGMENT_EXTRAS,
} from "../helpers/skeleton-config";
import { resolvePoint } from "../helpers/virtual-points";
import { SKELETON_COLORS } from "../helpers/skeleton-colors";

const ARUCO_EDGES: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 0]];

// Per-category line widths (px). Body includes charuco / aruco calibration markers.
const BODY_CONNECTION_LINE_WIDTH = 2;
const HAND_CONNECTION_LINE_WIDTH = 1.5;
const FACE_CONNECTION_LINE_WIDTH = 1;

type SegmentCategory = "body" | "hand" | "face";

function classifySegment(proximal: string, distal: string): SegmentCategory {
    const pk = classifyPointName(proximal);
    const dk = classifyPointName(distal);
    const rank: Record<string, number> = {
        face: 5, left_hand: 4, right_hand: 4, left: 3, right: 3, aruco: 2, center: 1,
    };
    const best = (rank[pk] ?? 0) >= (rank[dk] ?? 0) ? pk : dk;
    if (best === "face") return "face";
    if (best === "left_hand" || best === "right_hand") return "hand";
    return "body";
}

/** Per-layer state: geometry, material, the mesh object, and segment write info. */
interface ConnectionLayer {
    lineObj: LineSegments2;
    geo: LineSegmentsGeometry;
    mat: LineMaterial;
    /** Maps write-slot index → index in the flat `segments`/`colors` arrays. */
    segmentIndices: Int32Array;
}

/**
 * Renders skeleton connections as colored line segments at per-category widths.
 *
 * Body, hand, and face connections each get their own LineMaterial with a
 * different `linewidth`, because the shader-based approach uses a uniform —
 * one width per draw call. Charuco grid and aruco outlines are appended to the
 * body layer.
 */
export function ConnectionRenderer() {
    const { activeTrackerId, trackerSchemas, calibrationConfig } = useWorkerData();
    const { subscribeToKeypoints, subscribeToSkeleton } = useKeypointsSource();

    // Precompute charuco grid segment name-pairs — the grid topology depends
    // only on board dimensions, so this memoizes it and avoids recomputing
    // string templates + nested loops on every animation frame.
    const charucoSegments = useMemo(() => {
        const segs: { cornerA: string; cornerB: string }[] = [];
        const sx = calibrationConfig.charucoBoard.squares_x;
        const sy = calibrationConfig.charucoBoard.squares_y;
        if (sx < 2 || sy < 2) return segs;
        const cols = sx - 1;
        const rows = sy - 1;
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const id = r * cols + c;
                if (c < cols - 1) {
                    segs.push({ cornerA: `CharucoCorner-${id}`, cornerB: `CharucoCorner-${id + 1}` });
                }
                if (r < rows - 1) {
                    segs.push({ cornerA: `CharucoCorner-${id}`, cornerB: `CharucoCorner-${id + cols}` });
                }
            }
        }
        return segs;
    }, [calibrationConfig.charucoBoard.squares_x, calibrationConfig.charucoBoard.squares_y]);
    const { statsRef } = useViewportState();
    const { invalidate, size } = useThree();

    const pointsRef = useRef<Map<string, Point3d>>(new Map());
    const arucoMarkersRef = useRef<Map<number, (Point3d | undefined)[]>>(new Map());
    const prevArucoNamesRef = useRef<Set<string>>(new Set());
    const arucoNameCacheRef = useRef<Map<string, {markerId: number; cornerIdx: number}>>(new Map());
    const dirtyRef = useRef(false);
    const arucoChangedRef = useRef(true); // true on first frame to force build

    // Previous frame segment counts — used to short-circuit tail zeroing.
    // Tail slots are pre-filled with 1e5/0 at buffer creation and only need
    // zeroing when segments are REMOVED (rare). In steady state, zeroing
    // is skipped, saving ~18,000 Float32Array writes/frame.
    const prevBodySegIdxRef = useRef(0);
    const prevHandSegIdxRef = useRef(0);
    const prevFaceSegIdxRef = useRef(0);

    // Build the segment list whenever the active schema changes.
    const activeSchema = useMemo(() => {
        if (!activeTrackerId) return null;
        return trackerSchemas[activeTrackerId] ?? null;
    }, [activeTrackerId, trackerSchemas]);

    const {segments, colors: allColors} = useMemo(
        () => buildSegmentsFromSchema(activeSchema),
        [activeSchema],
    );

    // Split schema segments into per-category index arrays.
    const binned = useMemo(() => {
        const body: number[] = [];
        const hand: number[] = [];
        const face: number[] = [];
        for (let i = 0; i < segments.length; i++) {
            const cat = classifySegment(segments[i].proximal, segments[i].distal);
            if (cat === "face") face.push(i);
            else if (cat === "hand") hand.push(i);
            else body.push(i);
        }
        return {
            body: new Int32Array(body),
            hand: new Int32Array(hand),
            face: new Int32Array(face),
        };
    }, [segments]);

    // ---------- Body layer (includes charuco + aruco headroom) ----------
    const bodyGeoSegments = binned.body.length + MAX_SEGMENT_EXTRAS;

    const bodyGeo = useMemo(() => {
        const g = new LineSegmentsGeometry();
        g.setPositions(new Float32Array(bodyGeoSegments * 2 * 3).fill(1e5));
        g.setColors(new Float32Array(bodyGeoSegments * 2 * 3).fill(0));
        return g;
    }, [bodyGeoSegments]);

    const bodyMat = useMemo(() => new LineMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        linewidth: BODY_CONNECTION_LINE_WIDTH,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);

    const [bodyObj] = useState(() => new LineSegments2());

    useEffect(() => () => { bodyGeo.dispose(); bodyMat.dispose(); }, [bodyGeo, bodyMat]);

    // ---------- Hand layer ----------
    const handGeo = useMemo(() => {
        const g = new LineSegmentsGeometry();
        const n = binned.hand.length || 1; // never zero — LineSegmentsGeometry needs ≥1 segment
        g.setPositions(new Float32Array(n * 2 * 3).fill(1e5));
        g.setColors(new Float32Array(n * 2 * 3).fill(0));
        return g;
    }, [binned.hand.length]);

    const handMat = useMemo(() => new LineMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        linewidth: HAND_CONNECTION_LINE_WIDTH,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);

    const [handObj] = useState(() => new LineSegments2());

    useEffect(() => () => { handGeo.dispose(); handMat.dispose(); }, [handGeo, handMat]);

    // ---------- Face layer ----------
    const faceGeo = useMemo(() => {
        const g = new LineSegmentsGeometry();
        const n = binned.face.length || 1;
        g.setPositions(new Float32Array(n * 2 * 3).fill(1e5));
        g.setColors(new Float32Array(n * 2 * 3).fill(0));
        return g;
    }, [binned.face.length]);

    const faceMat = useMemo(() => new LineMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        linewidth: FACE_CONNECTION_LINE_WIDTH,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);

    const [faceObj] = useState(() => new LineSegments2());

    useEffect(() => () => { faceGeo.dispose(); faceMat.dispose(); }, [faceGeo, faceMat]);

    // Populate helpers shared by both subscriptions.
    const CHARUCO_PREFIX = "CharucoCorner-";
    const ARUCO_PREFIX = "ArucoMarkerCorner-";
    const isCalibPoint = (name: string) =>
        name.startsWith(CHARUCO_PREFIX) || name.startsWith(ARUCO_PREFIX);

    const populateMap = (
        m: Map<string, Point3d>,
        frame: KeypointsFrame,
        clearCalibFirst = false,
    ) => {
        if (clearCalibFirst) {
            for (const key of m.keys()) {
                if (isCalibPoint(key)) m.delete(key);
            }
        }
        const { pointNames, interleaved } = frame;
        for (let i = 0; i < pointNames.length; i++) {
            const off = i * 4;
            if (!interleaved[off + 3]) continue;
            const x = interleaved[off];
            const y = interleaved[off + 1];
            const z = interleaved[off + 2];
            if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z)) {
                m.set(pointNames[i], { x, y, z });
            }
        }
    };

    // Skeleton: FABRIK-fitted canonical body + hand landmarks. These drive
    // the stick-figure connections. Each frame replaces the body/hand entries
    // in pointsRef.
    useEffect(() => {
        return subscribeToSkeleton((frame: KeypointsFrame) => {
            const m = pointsRef.current;
            // Remove only body/hand entries (keep calibration points).
            for (const name of m.keys()) {
                if (!isCalibPoint(name)) m.delete(name);
            }
            populateMap(m, frame);
            dirtyRef.current = true;
            invalidate();
        });
    }, [subscribeToSkeleton, invalidate]);

    // Keypoints: calibration markers (charuco corners, aruco marker corners)
    // are the only points from the keypoints stream that contribute to
    // connection geometry. Skeleton body/hand positions come from the
    // skeleton subscription above.
    useEffect(() => {
        return subscribeToKeypoints((frame: KeypointsFrame) => {
            const hasCalib = frame.pointNames.some(isCalibPoint);
            if (!hasCalib) return;
            populateMap(pointsRef.current, frame, true);

            // Detect aruco name changes — O(N_incoming)
            const prevNames = prevArucoNamesRef.current;
            const incomingAruco: string[] = [];
            for (const name of frame.pointNames) {
                if (name.startsWith(ARUCO_PREFIX)) incomingAruco.push(name);
            }
            if (incomingAruco.length !== prevNames.size) {
                arucoChangedRef.current = true;
            } else {
                for (const n of incomingAruco) {
                    if (!prevNames.has(n)) { arucoChangedRef.current = true; break; }
                }
            }

            dirtyRef.current = true;
            invalidate();
        });
    }, [subscribeToKeypoints, invalidate]);

    /** Write one category of schema segments into a layer's geometry buffer. */
    function writeSegments(
        pos: Float32Array,
        col: Float32Array,
        indices: Int32Array,
    ): number {
        let visible = 0;
        for (let slot = 0; slot < indices.length; slot++) {
            const i = indices[slot];
            const seg = segments[i];
            const a = resolvePoint(pointsRef.current, seg.proximal, activeSchema);
            const b = resolvePoint(pointsRef.current, seg.distal, activeSchema);
            const base = slot * 6;
            const c = allColors[i];

            const aOk = a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z);
            const bOk = b && Number.isFinite(b.x) && Number.isFinite(b.y) && Number.isFinite(b.z);
            if (aOk && bOk) {
                pos[base] = a.x; pos[base + 1] = a.y; pos[base + 2] = a.z;
                pos[base + 3] = b.x; pos[base + 4] = b.y; pos[base + 5] = b.z;
                col[base] = c.r; col[base + 1] = c.g; col[base + 2] = c.b;
                col[base + 3] = c.r; col[base + 4] = c.g; col[base + 5] = c.b;
                visible++;
            } else {
                for (let j = 0; j < 6; j++) pos[base + j] = 1e5;
                for (let j = 0; j < 6; j++) col[base + j] = 0;
            }
        }
        return visible;
    }

    useFrame(() => {
        if (!dirtyRef.current) return;
        const t0 = performance.now();
        let visibleCount = 0;

        // ---- body layer (schema body segments + charuco + aruco) ----
        const bodyPosAttr = bodyGeo.attributes.instanceStart as InterleavedBufferAttribute;
        const bodyColAttr = bodyGeo.attributes.instanceColorStart as InterleavedBufferAttribute;
        const bodyPos = bodyPosAttr.data.array as Float32Array;
        const bodyCol = bodyColAttr.data.array as Float32Array;

        visibleCount += writeSegments(bodyPos, bodyCol, binned.body);

        // Charuco grid connections — iterate precomputed segment name-pairs
        // (memoized above, only rebuilt when board dimensions change).
        const pts = pointsRef.current;
        let segIdx = binned.body.length;
        const cr = SKELETON_COLORS.charuco.r;
        const cg = SKELETON_COLORS.charuco.g;
        const cb = SKELETON_COLORS.charuco.b;
        const maxBodySlots = binned.body.length + MAX_SEGMENT_EXTRAS;

        for (let i = 0; i < charucoSegments.length && segIdx < maxBodySlots; i++) {
            const { cornerA, cornerB } = charucoSegments[i];
            const a = pts.get(cornerA);
            const b = pts.get(cornerB);
            const base = segIdx * 6;
            const aOk = a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z);
            const bOk = b && Number.isFinite(b.x) && Number.isFinite(b.y) && Number.isFinite(b.z);
            if (aOk && bOk) {
                bodyPos[base]     = a.x; bodyPos[base + 1] = a.y; bodyPos[base + 2] = a.z;
                bodyPos[base + 3] = b.x; bodyPos[base + 4] = b.y; bodyPos[base + 5] = b.z;
                bodyCol[base] = cr; bodyCol[base + 1] = cg; bodyCol[base + 2] = cb;
                bodyCol[base + 3] = cr; bodyCol[base + 4] = cg; bodyCol[base + 5] = cb;
                visibleCount++;
            } else {
                for (let j = 0; j < 6; j++) bodyPos[base + j] = 1e5;
                for (let j = 0; j < 6; j++) bodyCol[base + j] = 0;
            }
            segIdx++;
        }

        // Aruco marker outline squares — 4 orange edges per detected marker.
        const ar = SKELETON_COLORS.aruco.r;
        const ag = SKELETON_COLORS.aruco.g;
        const ab = SKELETON_COLORS.aruco.b;

        const ARUCO_PREFIX = "ArucoMarkerCorner-";
        const arucoMarkers = arucoMarkersRef.current;
        const nameCache = arucoNameCacheRef.current;

        // Only rebuild the marker map when aruco names changed (detected in the
        // raw subscription callback). In steady state, just update corner
        // positions by iterating the name cache directly — O(A) where A=4-16.
        if (arucoChangedRef.current) {
            arucoChangedRef.current = false;
            arucoMarkers.clear();
            prevArucoNamesRef.current.clear();
            nameCache.clear();
            for (const [name, pt] of pts.entries()) {
                if (!name.startsWith(ARUCO_PREFIX)) continue;
                prevArucoNamesRef.current.add(name);
                const rest = name.slice(ARUCO_PREFIX.length);
                const sep = rest.indexOf("-");
                if (sep === -1) continue;
                const markerId = parseInt(rest.slice(0, sep));
                const cornerIdx = parseInt(rest.slice(sep + 1));
                nameCache.set(name, {markerId, cornerIdx});
                if (!arucoMarkers.has(markerId)) {
                    arucoMarkers.set(markerId, [undefined, undefined, undefined, undefined]);
                }
                arucoMarkers.get(markerId)![cornerIdx] = pt;
            }
        } else {
            for (const [name, cached] of nameCache) {
                const pt = pts.get(name);
                if (!pt) continue;
                const corners = arucoMarkers.get(cached.markerId);
                if (corners) corners[cached.cornerIdx] = pt;
            }
        }

        for (const corners of arucoMarkers.values()) {
            for (const [i, j] of ARUCO_EDGES) {
                if (segIdx >= maxBodySlots) break;
                const a = corners[i];
                const b = corners[j];
                const base = segIdx * 6;
                const aOk = a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z);
                const bOk = b && Number.isFinite(b.x) && Number.isFinite(b.y) && Number.isFinite(b.z);
                if (aOk && bOk) {
                    bodyPos[base]     = a.x; bodyPos[base + 1] = a.y; bodyPos[base + 2] = a.z;
                    bodyPos[base + 3] = b.x; bodyPos[base + 4] = b.y; bodyPos[base + 5] = b.z;
                    bodyCol[base]     = ar; bodyCol[base + 1] = ag; bodyCol[base + 2] = ab;
                    bodyCol[base + 3] = ar; bodyCol[base + 4] = ag; bodyCol[base + 5] = ab;
                    visibleCount++;
                } else {
                    for (let k = 0; k < 6; k++) bodyPos[base + k] = 1e5;
                    for (let k = 0; k < 6; k++) bodyCol[base + k] = 0;
                }
                segIdx++;
            }
        }

        // Zero out tail slots only when segments were removed (rare).
        // The buffer is pre-filled with 1e5/0 — slots never written to
        // are already zero. Only newly-unused slots need clearing.
        if (segIdx < prevBodySegIdxRef.current) {
            for (let i = segIdx; i < prevBodySegIdxRef.current; i++) {
                const base = i * 6;
                for (let j = 0; j < 6; j++) bodyPos[base + j] = 1e5;
                for (let j = 0; j < 6; j++) bodyCol[base + j] = 0;
            }
        }
        prevBodySegIdxRef.current = segIdx;

        bodyPosAttr.needsUpdate = true;
        bodyColAttr.needsUpdate = true;

        // ---- hand layer ----
        if (binned.hand.length > 0) {
            const hPosAttr = handGeo.attributes.instanceStart as InterleavedBufferAttribute;
            const hColAttr = handGeo.attributes.instanceColorStart as InterleavedBufferAttribute;
            const hPos = hPosAttr.data.array as Float32Array;
            const hCol = hColAttr.data.array as Float32Array;
            visibleCount += writeSegments(hPos, hCol, binned.hand);
            const handSegIdx = binned.hand.length;
            if (handSegIdx < prevHandSegIdxRef.current) {
                for (let i = handSegIdx; i < prevHandSegIdxRef.current; i++) {
                    const base = i * 6;
                    for (let j = 0; j < 6; j++) hPos[base + j] = 1e5;
                    for (let j = 0; j < 6; j++) hCol[base + j] = 0;
                }
            }
            prevHandSegIdxRef.current = handSegIdx;
            hPosAttr.needsUpdate = true;
            hColAttr.needsUpdate = true;
        }

        // ---- face layer ----
        if (binned.face.length > 0) {
            const fPosAttr = faceGeo.attributes.instanceStart as InterleavedBufferAttribute;
            const fColAttr = faceGeo.attributes.instanceColorStart as InterleavedBufferAttribute;
            const fPos = fPosAttr.data.array as Float32Array;
            const fCol = fColAttr.data.array as Float32Array;
            visibleCount += writeSegments(fPos, fCol, binned.face);
            const faceSegIdx = binned.face.length;
            if (faceSegIdx < prevFaceSegIdxRef.current) {
                for (let i = faceSegIdx; i < prevFaceSegIdxRef.current; i++) {
                    const base = i * 6;
                    for (let j = 0; j < 6; j++) fPos[base + j] = 1e5;
                    for (let j = 0; j < 6; j++) fCol[base + j] = 0;
                }
            }
            prevFaceSegIdxRef.current = faceSegIdx;
            fPosAttr.needsUpdate = true;
            fColAttr.needsUpdate = true;
        }

        dirtyRef.current = false;
        statsRef.current.connections = visibleCount;
        const elapsed = performance.now() - t0;
        if (elapsed > 8) console.warn(`ConnectionRenderer useFrame: ${elapsed.toFixed(1)}ms`);
    });

    return (
        <>
            <primitive object={bodyObj} frustumCulled={false}>
                <primitive object={bodyGeo} attach="geometry" />
                <primitive object={bodyMat} attach="material" />
            </primitive>
            {binned.hand.length > 0 && (
                <primitive object={handObj} frustumCulled={false}>
                    <primitive object={handGeo} attach="geometry" />
                    <primitive object={handMat} attach="material" />
                </primitive>
            )}
            {binned.face.length > 0 && (
                <primitive object={faceObj} frustumCulled={false}>
                    <primitive object={faceGeo} attach="geometry" />
                    <primitive object={faceMat} attach="material" />
                </primitive>
            )}
        </>
    );
}
