import { useEffect, useMemo, useRef } from "react";
import {
    BufferAttribute,
    BufferGeometry,
    LineBasicMaterial,
    LineSegments,
} from "three";
import { useFrame } from "@react-three/fiber";
import { useServer } from "@/services";
import { Point3d } from "@/components/viewport3d";
import { useKeypointsSource } from "../KeypointsSourceContext";
import { useViewportState } from "../scene/ViewportStateContext";
import {
    buildSegmentsFromSchema,
    MAX_SEGMENT_EXTRAS,
} from "../helpers/skeleton-config";
import { resolvePoint } from "../helpers/virtual-points";
import { useAppSelector } from "@/store";
import { selectCalibrationConfig } from "@/store/slices/calibration/calibration-slice";
import { SKELETON_COLORS } from "../helpers/skeleton-colors";

/**
 * Renders skeleton connections as colored line segments.
 *
 * Segments are derived from the active `TrackedObjectDefinition` pushed from
 * the backend via the `tracker_schemas` WS handshake. Charuco grid
 * connections are appended in a reserved tail region of the same buffer.
 */
export function ConnectionRenderer() {
    const { getActiveSchema, activeTrackerId, trackerSchemas } = useServer();
    const { subscribeToKeypointsRaw } = useKeypointsSource();
    const { statsRef } = useViewportState();
    const calibrationConfig = useAppSelector(selectCalibrationConfig);

    const linesRef = useRef<LineSegments>(null);
    const pointsRef = useRef<Map<string, Point3d>>(new Map());
    const dirtyRef = useRef(false);

    // Build the segment list whenever the active schema changes.
    const activeSchema = useMemo(() => {
        if (!activeTrackerId) return null;
        return trackerSchemas[activeTrackerId] ?? null;
    }, [activeTrackerId, trackerSchemas]);

    const {segments, colors} = useMemo(
        () => buildSegmentsFromSchema(activeSchema),
        [activeSchema],
    );

    const maxSegments = useMemo(
        () => segments.length + MAX_SEGMENT_EXTRAS,
        [segments.length],
    );

    const geo = useMemo(() => {
        const g = new BufferGeometry();
        const n = maxSegments * 2; // 2 vertices per segment
        g.setAttribute("position", new BufferAttribute(new Float32Array(n * 3).fill(1e5), 3));
        g.setAttribute("color",    new BufferAttribute(new Float32Array(n * 3).fill(0),   3));
        return g;
    }, [maxSegments]);

    const mat = useMemo(() => new LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
    }), []);

    useEffect(() => {
        return subscribeToKeypointsRaw((allPts: Record<string, Point3d>) => {
            const map = new Map<string, Point3d>();
            for (const [name, pt] of Object.entries(allPts)) {
                map.set(name, pt);
            }
            pointsRef.current = map;
            dirtyRef.current = true;
        });
    }, [subscribeToKeypointsRaw]);

    useFrame(() => {
        if (!dirtyRef.current) return;
        const pts = pointsRef.current;
        const positions = geo.attributes.position.array as Float32Array;
        const vertexColors = geo.attributes.color.array as Float32Array;

        let visibleCount = 0;

        for (let i = 0; i < segments.length; i++) {
            const seg = segments[i];
            const a = resolvePoint(pts, seg.proximal, activeSchema);
            const b = resolvePoint(pts, seg.distal, activeSchema);
            const base = i * 6;
            const c = colors[i];

            const aOk = a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z);
            const bOk = b && Number.isFinite(b.x) && Number.isFinite(b.y) && Number.isFinite(b.z);
            if (aOk && bOk) {
                positions[base]     = a.x; positions[base + 1] = a.y; positions[base + 2] = a.z;
                positions[base + 3] = b.x; positions[base + 4] = b.y; positions[base + 5] = b.z;
                vertexColors[base]     = c.r; vertexColors[base + 1] = c.g; vertexColors[base + 2] = c.b;
                vertexColors[base + 3] = c.r; vertexColors[base + 4] = c.g; vertexColors[base + 5] = c.b;
                visibleCount++;
            } else {
                for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
                for (let j = 0; j < 6; j++) vertexColors[base + j] = 0;
            }
        }

        // Charuco grid connections — appended after the schema-driven segments.
        const cols = calibrationConfig.charucoBoard.squares_x - 1;
        const rows = calibrationConfig.charucoBoard.squares_y - 1;
        let segIdx = segments.length;
        const cr = SKELETON_COLORS.charuco.r;
        const cg = SKELETON_COLORS.charuco.g;
        const cb = SKELETON_COLORS.charuco.b;

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const id = r * cols + c;
                const pt = pts.get(`CharucoCorner-${id}`);

                if (c < cols - 1 && segIdx < maxSegments) {
                    const right = pts.get(`CharucoCorner-${id + 1}`);
                    const base = segIdx * 6;
                    if (pt && right) {
                        positions[base]     = pt.x;    positions[base + 1] = pt.y;    positions[base + 2] = pt.z;
                        positions[base + 3] = right.x; positions[base + 4] = right.y; positions[base + 5] = right.z;
                        vertexColors[base] = cr; vertexColors[base + 1] = cg; vertexColors[base + 2] = cb;
                        vertexColors[base + 3] = cr; vertexColors[base + 4] = cg; vertexColors[base + 5] = cb;
                        visibleCount++;
                    } else {
                        for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
                        for (let j = 0; j < 6; j++) vertexColors[base + j] = 0;
                    }
                    segIdx++;
                }

                if (r < rows - 1 && segIdx < maxSegments) {
                    const below = pts.get(`CharucoCorner-${id + cols}`);
                    const base = segIdx * 6;
                    if (pt && below) {
                        positions[base]     = pt.x;    positions[base + 1] = pt.y;    positions[base + 2] = pt.z;
                        positions[base + 3] = below.x; positions[base + 4] = below.y; positions[base + 5] = below.z;
                        vertexColors[base] = cr; vertexColors[base + 1] = cg; vertexColors[base + 2] = cb;
                        vertexColors[base + 3] = cr; vertexColors[base + 4] = cg; vertexColors[base + 5] = cb;
                        visibleCount++;
                    } else {
                        for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
                        for (let j = 0; j < 6; j++) vertexColors[base + j] = 0;
                    }
                    segIdx++;
                }
            }
        }

        // Zero out any unused tail slots so stale data doesn't render.
        for (let i = segIdx; i < maxSegments; i++) {
            const base = i * 6;
            for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
            for (let j = 0; j < 6; j++) vertexColors[base + j] = 0;
        }

        geo.attributes.position.needsUpdate = true;
        geo.attributes.color.needsUpdate = true;
        dirtyRef.current = false;
        statsRef.current.connections = visibleCount;
    });

    return (
        <lineSegments ref={linesRef} geometry={geo} material={mat} frustumCulled={false} />
    );
}
