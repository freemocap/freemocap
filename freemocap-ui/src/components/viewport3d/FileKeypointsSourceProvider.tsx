import React, {useEffect, useMemo, useRef} from "react";
import {parquetRead} from "hyparquet";
import type {DecodedArray} from "hyparquet";
import {
    KeypointsCallback,
    KeypointsFrame,
    KeypointsSource,
    KeypointsSourceProvider,
} from "./KeypointsSourceContext";
import {serverUrls} from "@/constants/server-urls";
import {VIEWPORT_WORKER} from "./ThreeJsCanvas";
import {useAppDispatch, useAppSelector} from "@/store";
import {fetchPlaybackBundle, selectPlaybackBundle} from "@/store/slices/playback-data/playback-data-slice";
import {calibrationLoadedFromBundle} from "@/store/slices/calibration/calibration-slice";

/**
 * KeypointsSource implementation that reads the recording's long-format
 * `freemocap_data_by_frame.parquet` directly in the browser (via hyparquet),
 * pivots long→wide into per-trajectory Float32Array buffers, and emits
 * per-frame KeypointsFrame values in lockstep with the playback slider.
 *
 * Design notes:
 *   - Uses parquetRead (columnar API) instead of parquetReadObjects to read column-wise.
 *   - After decode, each trajectory is packed as Float32Array of length
 *     frameCount * K * 3, giving O(1) per-frame indexing.
 *   - Subscribers receive a stable KeypointsFrame whose `scratchInterleaved`
 *     buffer is mutated in place each tick (zero GC pressure after first frame).
 *   - Driven by `currentFrameRef` from usePlaybackController, polled via our
 *     own rAF loop. React re-renders are not involved in the hot path.
 */

type TrajectoryAlias = "raw" | "filtered";

const TRAJECTORY_PARQUET_VALUE: Record<TrajectoryAlias, string> = {
    raw: "3d_xyz",
    filtered: "rigid_3d_xyz",
};

const ParquetColumnNames = {
    frame:      "frame",
    keypoint:   "keypoint",
    model:      "model",
    x:          "x",
    y:          "y",
    z:          "z",
    trajectory: "trajectory",
} as const;

interface TrajectoryData {
    names: readonly string[];
    buffer: Float32Array;              // length = frameCount * K * 3 (x, y, z — no vis in parquet)
    frameCount: number;
    keypointCount: number;
    scratchInterleaved: Float32Array;  // length = K * 4 (x, y, z, vis) — mutated each tick
    scratchFrame: KeypointsFrame;      // stable reference — interleaved points at scratchInterleaved
    subscribers: Set<KeypointsCallback>;
    lastEmittedFrame: number;          // -1 means "never emitted"
}

function emptyTrajectory(): TrajectoryData {
    const scratchInterleaved = new Float32Array(0);
    return {
        names: [],
        buffer: new Float32Array(0),
        frameCount: 0,
        keypointCount: 0,
        scratchInterleaved,
        scratchFrame: { pointNames: [], interleaved: scratchInterleaved },
        subscribers: new Set(),
        lastEmittedFrame: -1,
    };
}

// Helper to check if a value is a BigInt
function isBigInt(value: unknown): value is bigint {
    return typeof value === "bigint";
}

// Helper to convert any BigInt-containing array to Float64Array
function convertBigIntArray(arr: DecodedArray): Float64Array | DecodedArray {
    if (arr instanceof BigInt64Array || arr instanceof BigUint64Array) {
        const out = new Float64Array(arr.length);
        for (let i = 0; i < arr.length; i++) {
            out[i] = Number(arr[i]);
        }
        return out;
    }
    // Check if plain array contains BigInt values
    if (Array.isArray(arr) && arr.length > 0 && isBigInt(arr[0])) {
        const out = new Float64Array(arr.length);
        for (let i = 0; i < arr.length; i++) {
            out[i] = Number(arr[i]);
        }
        return out;
    }
    return arr;
}

// Merge row-group chunks for a single column into one contiguous array.
function concatDecodedArrays(chunks: DecodedArray[]): DecodedArray {
    // First, convert any BigInt arrays to Float64Array
    const converted = chunks.map(c => convertBigIntArray(c));

    // Even for a single chunk, check if it was a BigInt array (already converted above)
    if (converted.length === 1) {
        return converted[0];
    }

    const total = converted.reduce((s, c) => s + c.length, 0);
    const first = converted[0];
    if (first instanceof Float64Array) {
        const out = new Float64Array(total);
        let off = 0;
        for (const c of converted) { out.set(c as Float64Array, off); off += c.length; }
        return out;
    }
    if (first instanceof Float32Array) {
        const out = new Float32Array(total);
        let off = 0;
        for (const c of converted) { out.set(c as Float32Array, off); off += c.length; }
        return out;
    }
    if (first instanceof Int32Array) {
        const out = new Int32Array(total);
        let off = 0;
        for (const c of converted) { out.set(c as Int32Array, off); off += c.length; }
        return out;
    }
    // String columns or other arrays
    const out: unknown[] = [];
    for (const c of converted) for (let i = 0; i < c.length; i++) out.push((c as unknown[])[i]);
    return out;
}

/**
 * Prefix hand keypoint names with their side so they match the holistic schema's
 * connection endpoint names. Body and face names are returned unchanged — they
 * already carry any needed prefix baked into the landmark name itself.
 *
 *   mediapipe.right_hand + wrist → right_hand_wrist
 *   mediapipe.left_hand  + wrist → left_hand_wrist
 *   mediapipe.body       + nose  → nose
 */
function prefixKeypointName(keypoint: string, model: string): string {
    const dot = model.indexOf(".");
    if (dot === -1) return keypoint;
    const aspect = model.slice(dot + 1);
    if (aspect === "right_hand" || aspect === "left_hand") {
        return `${aspect}_${keypoint}`;
    }
    return keypoint;
}

function buildTrajectory(
    cols: Record<string, DecodedArray>,
    parquetValue: string,
    frameCount: number,
): TrajectoryData {
    // Frame column may be Int32Array or Float64Array (if converted from BigInt)
    const frameCol = cols[ParquetColumnNames.frame] as Int32Array | Float64Array;
    const keypointCol = cols[ParquetColumnNames.keypoint] as string[];
    const modelCol = cols[ParquetColumnNames.model] as string[];
    const xCol = cols[ParquetColumnNames.x] as Float64Array;
    const yCol = cols[ParquetColumnNames.y] as Float64Array;
    const zCol = cols[ParquetColumnNames.z] as Float64Array;
    const trajCol = cols[ParquetColumnNames.trajectory] as string[];
    const rowCount = frameCol.length;

    // First pass: collect unique keypoint names for this trajectory.
    // Hand keypoints are prefixed with their side (right_hand_ / left_hand_)
    // so left and right don't collide in the flat name set and so the names
    // match the holistic schema's connection endpoint names.
    const nameSet = new Set<string>();
    for (let i = 0; i < rowCount; i++) {
        if (trajCol[i] === parquetValue) {
            nameSet.add(prefixKeypointName(keypointCol[i], modelCol[i]));
        }
    }
    if (nameSet.size === 0) return emptyTrajectory();

    const names = Array.from(nameSet).sort();
    const nameToIdx = new Map<string, number>();
    for (let i = 0; i < names.length; i++) nameToIdx.set(names[i], i);

    const K = names.length;
    const buffer = new Float32Array(frameCount * K * 3);
    buffer.fill(NaN);

    // Second pass: scatter columnar data into the packed buffer.
    for (let i = 0; i < rowCount; i++) {
        if (trajCol[i] !== parquetValue) continue;
        const f = frameCol[i];
        if (f < 0 || f >= frameCount) continue;
        const k = nameToIdx.get(prefixKeypointName(keypointCol[i], modelCol[i]));
        if (k === undefined) continue;
        const off = (f * K + k) * 3;
        buffer[off]     = xCol[i];
        buffer[off + 1] = yCol[i];
        buffer[off + 2] = zCol[i];
    }

    const scratchInterleaved = new Float32Array(K * 4);
    const scratchFrame: KeypointsFrame = { pointNames: names, interleaved: scratchInterleaved };

    return {
        names,
        buffer,
        frameCount,
        keypointCount: K,
        scratchInterleaved,
        scratchFrame,
        subscribers: new Set(),
        lastEmittedFrame: -1,
    };
}

/**
 * Rewrite sequential face_XXXX names produced by skellyforge's model_info
 * (face_0000…face_0135) into the non-contiguous MediaPipe contour-index names
 * from the tracker schema (face_0000, face_0007, face_0010…).  The buffer is
 * indexed by position, not name, so only the name list changes — per-frame data
 * stays correct. After this, the schema's face-connection endpoint names match
 * the trajectory's point names and ConnectionRenderer can draw them.
 */
function remapTrajectoryFaceNames(
    traj: TrajectoryData,
    contourNames: string[],
): void {
    if (traj.frameCount === 0 || contourNames.length === 0) return;

    // Collect current face-name slots sorted by their sequential number.
    const slots: { idx: number; seq: number }[] = [];
    const names = traj.names as string[];
    for (let i = 0; i < names.length; i++) {
        if (names[i].startsWith("face_")) {
            const seq = parseInt(names[i].slice(5), 10);
            if (!Number.isNaN(seq)) slots.push({ idx: i, seq });
        }
    }
    slots.sort((a, b) => a.seq - b.seq);

    // Replace each sequential slot with the matching contour name.
    const newNames = [...names];
    for (let i = 0; i < slots.length && i < contourNames.length; i++) {
        newNames[slots[i].idx] = contourNames[i];
    }

    // Mutate in-place so existing refs pick up the new names.
    (traj as { names: readonly string[] }).names = newNames;
    (traj as { scratchFrame: KeypointsFrame }).scratchFrame = {
        pointNames: newNames,
        interleaved: traj.scratchInterleaved,
    };
}

function updateScratch(traj: TrajectoryData, frame: number): void {
    const K = traj.keypointCount;
    if (K === 0) return;
    const clamped = Math.max(0, Math.min(frame, traj.frameCount - 1));
    const base = clamped * K * 3;
    const buf = traj.buffer;
    const scratch = traj.scratchInterleaved;

    for (let k = 0; k < K; k++) {
        const srcOff = base + k * 3;
        const dstOff = k * 4;
        const x = buf[srcOff];
        const y = buf[srcOff + 1];
        const z = buf[srcOff + 2];
        scratch[dstOff]     = x;
        scratch[dstOff + 1] = y;
        scratch[dstOff + 2] = z;
        scratch[dstOff + 3] = Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z) ? 1.0 : 0.0;
    }
}

function fireSubscribers(traj: TrajectoryData): void {
    for (const cb of traj.subscribers) {
        cb(traj.scratchFrame);
    }
}

export const FileKeypointsSourceProvider: React.FC<{
    recordingId: string | null;
    recordingParentDirectory?: string | null;
    currentFrameRef: React.RefObject<number>;
    children: React.ReactNode;
}> = ({recordingId, recordingParentDirectory, currentFrameRef, children}) => {

    const rawRef = useRef<TrajectoryData>(emptyTrajectory());
    const filteredRef = useRef<TrajectoryData>(emptyTrajectory());
    const faceContourNamesRef = useRef<string[]>([]);
    const dispatch = useAppDispatch();

    // Fetch the playback bundle (calibration + tracker-schema + status) via
    // Redux thunk. The `condition` guard prevents duplicate requests when
    // StrictMode remounts the component.
    useEffect(() => {
        if (!recordingId) return;
        dispatch(fetchPlaybackBundle({
            recordingId,
            recordingParentDirectory,
        }));
    }, [recordingId, recordingParentDirectory, dispatch]);

    // When the bundle arrives from Redux, forward calibration + tracker-schema
    // to the viewport3d worker and populate the calibration Redux slice so
    // ThreeJsCanvas can also consume it.
    const bundle = useAppSelector(selectPlaybackBundle(recordingId));

    useEffect(() => {
        if (!bundle) return;

        // Forward tracker schema to the worker so ConnectionRenderer draws skeleton lines.
        const schemaName: string = (bundle.trackerSchema as any)?.name || "playback_schema";
        VIEWPORT_WORKER.postMessage({
            type: "schemaState",
            data: {
                activeTrackerId: schemaName,
                trackerSchemas: {[schemaName]: bundle.trackerSchema},
            },
        });

        // Remap sequential face_XXXX names to contour YAML names so schema
        // connections match the trajectory's point names.
        const tp: string[] = (bundle.trackerSchema as any)?.tracked_points ?? [];
        faceContourNamesRef.current = tp.filter((n: string) => n.startsWith("face_"));
        if (faceContourNamesRef.current.length > 0) {
            remapTrajectoryFaceNames(rawRef.current, faceContourNamesRef.current);
            remapTrajectoryFaceNames(filteredRef.current, faceContourNamesRef.current);
            if (rawRef.current.lastEmittedFrame >= 0) {
                fireSubscribers(rawRef.current);
            }
            if (filteredRef.current.lastEmittedFrame >= 0) {
                fireSubscribers(filteredRef.current);
            }
        }

        // Populate the calibration Redux slice so ThreeJsCanvas consumes it.
        dispatch(calibrationLoadedFromBundle(bundle.calibration));
    }, [bundle, dispatch]);

    // Load + decode the parquet whenever recordingId changes.
    useEffect(() => {
        if (!recordingId) {
            rawRef.current = emptyTrajectory();
            filteredRef.current = emptyTrajectory();
            return;
        }

        const controller = new AbortController();

        (async () => {
            try {
                const baseUrl = serverUrls.getHttpUrl();
                const params = new URLSearchParams();
                if (recordingParentDirectory) {
                    params.set('recording_parent_directory', recordingParentDirectory);
                }
                const qs = params.toString();
                const url = `${baseUrl}/freemocap/playback/${encodeURIComponent(recordingId)}/parquet${qs ? `?${qs}` : ''}`;

                const t0 = performance.now();
                const resp = await fetch(url, {signal: controller.signal});
                if (!resp.ok) {
                    console.warn(`[FileKeypointsSource] parquet fetch failed: ${resp.status}`);
                    return;
                }
                const ab = await resp.arrayBuffer();
                const tFetched = performance.now();

                // Collect column chunks. onChunk fires once per column per row group,
                // so large files produce multiple chunks per column that must be merged.
                const chunkMap: Record<string, DecodedArray[]> = {};
                await parquetRead({
                    file: ab,
                    columns: Object.values(ParquetColumnNames),
                    onChunk: ({columnName, columnData}) => {
                        (chunkMap[columnName] ??= []).push(columnData);
                    },
                });
                const tDecoded = performance.now();

                if (controller.signal.aborted) return;

                // Merge row-group chunks into single contiguous arrays per column.
                const cols: Record<string, DecodedArray> = {};
                for (const name of Object.keys(chunkMap)) {
                    cols[name] = concatDecodedArrays(chunkMap[name]);
                }

                // Frame column may be Int32Array or Float64Array (if converted from BigInt)
                const frameCol = cols[ParquetColumnNames.frame] as Int32Array | Float64Array;
                let frameCount = 0;
                for (let i = 0; i < frameCol.length; i++) {
                    if (frameCol[i] > frameCount) frameCount = frameCol[i];
                }
                frameCount += 1;

                // Preserve existing subscribers across recording swaps.
                const rawSubs = rawRef.current.subscribers;
                const filteredSubs = filteredRef.current.subscribers;

                const rawTraj = buildTrajectory(cols, TRAJECTORY_PARQUET_VALUE.raw, frameCount);
                const filteredTraj = buildTrajectory(cols, TRAJECTORY_PARQUET_VALUE.filtered, frameCount);
                rawTraj.subscribers = rawSubs;
                filteredTraj.subscribers = filteredSubs;
                rawRef.current = rawTraj;
                filteredRef.current = filteredTraj;

                // If the playback-bundle schema arrived before the parquet finished
                // loading, remap face names now so the first emitted frame already has
                // correct contour-index names.
                if (faceContourNamesRef.current.length > 0) {
                    remapTrajectoryFaceNames(rawTraj, faceContourNamesRef.current);
                    remapTrajectoryFaceNames(filteredTraj, faceContourNamesRef.current);
                }

                const tBuilt = performance.now();
                console.info(
                    `[FileKeypointsSource] parquet ready: ${frameCol.length} rows, ${frameCount} frames, ` +
                    `raw K=${rawTraj.keypointCount}, filtered K=${filteredTraj.keypointCount} ` +
                    `(fetch ${(tFetched - t0) | 0}ms, decode ${(tDecoded - tFetched) | 0}ms, pivot ${(tBuilt - tDecoded) | 0}ms)`
                );

            } catch (err) {
                if ((err as any)?.name !== "AbortError") {
                    console.warn("[FileKeypointsSource] load error", err);
                }
            }
        })();

        return () => controller.abort();
    }, [recordingId, recordingParentDirectory]);

    // rAF loop: poll the controller's frame ref and push updates when the
    // integer frame changes.
    useEffect(() => {
        let raf = 0;

        const tick = () => {
            const frame = Math.floor(currentFrameRef.current);

            for (const traj of [rawRef.current, filteredRef.current]) {
                if (traj.frameCount === 0) continue;
                if (frame !== traj.lastEmittedFrame) {
                    updateScratch(traj, frame);
                    traj.lastEmittedFrame = frame;
                    fireSubscribers(traj);
                }
            }

            raf = requestAnimationFrame(tick);
        };

        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [currentFrameRef]);

    const source = useMemo<KeypointsSource>(() => ({
        subscribeToKeypointsRaw: (cb: KeypointsCallback) => {
            rawRef.current.subscribers.add(cb);
            if (rawRef.current.frameCount > 0 && rawRef.current.lastEmittedFrame >= 0) {
                cb(rawRef.current.scratchFrame);
            }
            return () => { rawRef.current.subscribers.delete(cb); };
        },
        subscribeToKeypointsFiltered: (cb: KeypointsCallback) => {
            filteredRef.current.subscribers.add(cb);
            if (filteredRef.current.frameCount > 0 && filteredRef.current.lastEmittedFrame >= 0) {
                cb(filteredRef.current.scratchFrame);
            }
            return () => { filteredRef.current.subscribers.delete(cb); };
        },
        getLatestKeypointsRaw: () =>
            rawRef.current.frameCount > 0 ? rawRef.current.scratchFrame : null,
    }), []);

    return (
        <KeypointsSourceProvider source={source}>
            {children}
        </KeypointsSourceProvider>
    );
};
