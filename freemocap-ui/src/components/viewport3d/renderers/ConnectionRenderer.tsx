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
import { useViewportState } from "../scene/ViewportStateContext";
import {
    SEGMENT_DEFINITIONS,
    SEGMENT_COLORS,
    MAX_SEGMENTS,
} from "../helpers/skeleton-config";
import { resolvePoint } from "../helpers/virtual-points";
import { useAppSelector } from "@/store";
import { selectCalibrationConfig } from "@/store/slices/calibration/calibration-slice";
import { SKELETON_COLORS } from "../helpers/skeleton-colors";

const SEGMENT_KEYS = Object.keys(SEGMENT_DEFINITIONS);

/**
 * Renders skeleton connections as colored line segments.
 * Uses per-vertex colors so each segment matches its body-part color scheme:
 *   left body = blue, right body = red, center = green,
 *   left hand = cyan, right hand = magenta, face = gold
 */
export function ConnectionRenderer() {
    const { subscribeToKeypointsRaw } = useServer();
    const { statsRef } = useViewportState();
    const calibrationConfig = useAppSelector(selectCalibrationConfig);

    const linesRef = useRef<LineSegments>(null);
    const pointsRef = useRef<Map<string, Point3d>>(new Map());
    const dirtyRef = useRef(false);

    const geo = useMemo(() => {
        const g = new BufferGeometry();
        const n = MAX_SEGMENTS * 2; // 2 vertices per segment
        g.setAttribute("position", new BufferAttribute(new Float32Array(n * 3).fill(1e5), 3));
        g.setAttribute("color",    new BufferAttribute(new Float32Array(n * 3).fill(0),   3));
        return g;
    }, []);

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
        const colors = geo.attributes.color.array as Float32Array;

        let visibleCount = 0;

        for (let i = 0; i < SEGMENT_KEYS.length; i++) {
            const seg = SEGMENT_DEFINITIONS[SEGMENT_KEYS[i]];
            const a = resolvePoint(pts, seg.proximal);
            const b = resolvePoint(pts, seg.distal);
            const base = i * 6;
            const c = SEGMENT_COLORS[i];

            if (a && b) {
                positions[base]     = a.x; positions[base + 1] = a.y; positions[base + 2] = a.z;
                positions[base + 3] = b.x; positions[base + 4] = b.y; positions[base + 5] = b.z;
                colors[base]     = c.r; colors[base + 1] = c.g; colors[base + 2] = c.b;
                colors[base + 3] = c.r; colors[base + 4] = c.g; colors[base + 5] = c.b;
                visibleCount++;
            } else {
                for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
                for (let j = 0; j < 6; j++) colors[base + j] = 0;
            }
        }

        // Charuco grid connections
        const cols = calibrationConfig.charucoBoard.squares_x - 1;
        const rows = calibrationConfig.charucoBoard.squares_y - 1;
        let segIdx = SEGMENT_KEYS.length;
        const cr = SKELETON_COLORS.charuco.r;
        const cg = SKELETON_COLORS.charuco.g;
        const cb = SKELETON_COLORS.charuco.b;

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const id = r * cols + c;
                const pt = pts.get(`CharucoCorner-${id}`);

                // Horizontal connection (to right neighbor)
                if (c < cols - 1) {
                    const right = pts.get(`CharucoCorner-${id + 1}`);
                    const base = segIdx * 6;
                    if (pt && right) {
                        positions[base]     = pt.x;    positions[base + 1] = pt.y;    positions[base + 2] = pt.z;
                        positions[base + 3] = right.x; positions[base + 4] = right.y; positions[base + 5] = right.z;
                        colors[base] = cr; colors[base + 1] = cg; colors[base + 2] = cb;
                        colors[base + 3] = cr; colors[base + 4] = cg; colors[base + 5] = cb;
                        visibleCount++;
                    } else {
                        for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
                        for (let j = 0; j < 6; j++) colors[base + j] = 0;
                    }
                    segIdx++;
                }

                // Vertical connection (to bottom neighbor)
                if (r < rows - 1) {
                    const below = pts.get(`CharucoCorner-${id + cols}`);
                    const base = segIdx * 6;
                    if (pt && below) {
                        positions[base]     = pt.x;    positions[base + 1] = pt.y;    positions[base + 2] = pt.z;
                        positions[base + 3] = below.x; positions[base + 4] = below.y; positions[base + 5] = below.z;
                        colors[base] = cr; colors[base + 1] = cg; colors[base + 2] = cb;
                        colors[base + 3] = cr; colors[base + 4] = cg; colors[base + 5] = cb;
                        visibleCount++;
                    } else {
                        for (let j = 0; j < 6; j++) positions[base + j] = 1e5;
                        for (let j = 0; j < 6; j++) colors[base + j] = 0;
                    }
                    segIdx++;
                }
            }
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
