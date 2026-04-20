import React, {useEffect, useMemo, useRef} from "react";
import {parquetReadObjects} from "hyparquet";
import {Point3d} from "./helpers/viewport3d-types";
import {
    KeypointsCallback,
    KeypointsSource,
    KeypointsSourceProvider,
} from "./KeypointsSourceContext";
import {serverUrls} from "@/constants/server-urls";

/**
 * KeypointsSource implementation that reads the recording's long-format
 * `freemocap_data_by_frame.parquet` directly in the browser (via hyparquet),
 * pivots long→wide into per-trajectory Float32Array buffers, and emits
 * per-frame point records in lockstep with the playback slider.
 *
 * Design notes:
 *   - Parquet is the canonical freemocap data format; decoding it client-side
 *     keeps the backend simple (one passthrough file endpoint) and avoids
 *     sibling cache artifacts that can drift from the source.
 *   - After decode, each trajectory is packed as Float32Array of length
 *     frameCount * K * 3, giving O(1) per-frame indexing.
 *   - Subscribers receive a pre-allocated scratch record whose Point3d slots
 *     are mutated in place each tick (zero GC pressure).
 *   - Driven by `currentFrameRef` from usePlaybackController, polled via our
 *     own rAF loop. React re-renders are not involved in the hot path.
 */

type TrajectoryAlias = "raw" | "filtered";

const TRAJECTORY_PARQUET_VALUE: Record<TrajectoryAlias, string> = {
    raw: "3d_xyz",
    filtered: "rigid_3d_xyz",
};

interface TrajectoryData {
    names: string[];
    buffer: Float32Array;           // length = frameCount * K * 3
    frameCount: number;
    keypointCount: number;
    scratch: Record<string, Point3d>;
    subscribers: Set<KeypointsCallback>;
    lastEmittedFrame: number;       // -1 means "never emitted"
}

interface ParquetRow {
    frame: number;
    keypoint: string;
    x: number;
    y: number;
    z: number;
    trajectory: string;
}

function emptyTrajectory(): TrajectoryData {
    return {
        names: [],
        buffer: new Float32Array(0),
        frameCount: 0,
        keypointCount: 0,
        scratch: {},
        subscribers: new Set(),
        lastEmittedFrame: -1,
    };
}

function buildTrajectory(
    rows: ParquetRow[],
    parquetValue: string,
    frameCount: number,
): TrajectoryData {
    // First pass: collect unique keypoint names for this trajectory.
    const nameSet = new Set<string>();
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        if (row.trajectory === parquetValue) nameSet.add(String(row.keypoint));
    }
    if (nameSet.size === 0) return emptyTrajectory();

    const names = Array.from(nameSet).sort();
    const nameToIdx = new Map<string, number>();
    for (let i = 0; i < names.length; i++) nameToIdx.set(names[i], i);

    const K = names.length;
    const buffer = new Float32Array(frameCount * K * 3);
    buffer.fill(NaN);

    // Second pass: scatter rows into the packed buffer.
    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        if (row.trajectory !== parquetValue) continue;
        const f = row.frame;
        if (f < 0 || f >= frameCount) continue;
        const k = nameToIdx.get(String(row.keypoint));
        if (k === undefined) continue;
        const off = (f * K + k) * 3;
        buffer[off] = row.x;
        buffer[off + 1] = row.y;
        buffer[off + 2] = row.z;
    }

    const scratch: Record<string, Point3d> = {};
    for (const name of names) scratch[name] = {x: NaN, y: NaN, z: NaN};

    return {
        names,
        buffer,
        frameCount,
        keypointCount: K,
        scratch,
        subscribers: new Set(),
        lastEmittedFrame: -1,
    };
}

function updateScratch(traj: TrajectoryData, frame: number): void {
    const K = traj.keypointCount;
    if (K === 0) return;
    const clamped = Math.max(0, Math.min(frame, traj.frameCount - 1));
    const base = clamped * K * 3;
    const buf = traj.buffer;
    const names = traj.names;
    const scratch = traj.scratch;

    for (let k = 0; k < K; k++) {
        const off = base + k * 3;
        const slot = scratch[names[k]];
        slot.x = buf[off];
        slot.y = buf[off + 1];
        slot.z = buf[off + 2];
    }
}

function fireSubscribers(traj: TrajectoryData): void {
    for (const cb of traj.subscribers) {
        cb(traj.scratch);
    }
}

export const FileKeypointsSourceProvider: React.FC<{
    recordingId: string | null;
    currentFrameRef: React.MutableRefObject<number>;
    children: React.ReactNode;
}> = ({recordingId, currentFrameRef, children}) => {

    const rawRef = useRef<TrajectoryData>(emptyTrajectory());
    const filteredRef = useRef<TrajectoryData>(emptyTrajectory());

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
                const url = `${baseUrl}/freemocap/playback/${encodeURIComponent(recordingId)}/parquet`;

                const t0 = performance.now();
                const resp = await fetch(url, {signal: controller.signal});
                if (!resp.ok) {
                    console.warn(`[FileKeypointsSource] parquet fetch failed: ${resp.status}`);
                    return;
                }
                const ab = await resp.arrayBuffer();
                const tFetched = performance.now();

                const rows = (await parquetReadObjects({
                    file: ab,
                    columns: ["frame", "keypoint", "x", "y", "z", "trajectory"],
                })) as ParquetRow[];
                const tDecoded = performance.now();

                if (controller.signal.aborted) return;

                let frameCount = 0;
                for (let i = 0; i < rows.length; i++) {
                    const f = rows[i].frame;
                    if (f > frameCount) frameCount = f;
                }
                frameCount += 1;

                // Preserve existing subscribers across recording swaps.
                const rawSubs = rawRef.current.subscribers;
                const filteredSubs = filteredRef.current.subscribers;

                const rawTraj = buildTrajectory(rows, TRAJECTORY_PARQUET_VALUE.raw, frameCount);
                const filteredTraj = buildTrajectory(rows, TRAJECTORY_PARQUET_VALUE.filtered, frameCount);
                rawTraj.subscribers = rawSubs;
                filteredTraj.subscribers = filteredSubs;
                rawRef.current = rawTraj;
                filteredRef.current = filteredTraj;

                const tBuilt = performance.now();
                console.info(
                    `[FileKeypointsSource] parquet ready: ${rows.length} rows, ${frameCount} frames, ` +
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
    }, [recordingId]);

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
                cb(rawRef.current.scratch);
            }
            return () => { rawRef.current.subscribers.delete(cb); };
        },
        subscribeToKeypointsFiltered: (cb: KeypointsCallback) => {
            filteredRef.current.subscribers.add(cb);
            if (filteredRef.current.frameCount > 0 && filteredRef.current.lastEmittedFrame >= 0) {
                cb(filteredRef.current.scratch);
            }
            return () => { filteredRef.current.subscribers.delete(cb); };
        },
        getLatestKeypointsRaw: () => rawRef.current.scratch,
    }), []);

    return (
        <KeypointsSourceProvider source={source}>
            {children}
        </KeypointsSourceProvider>
    );
};
