import { useEffect, useMemo, useRef } from "react";
import { BufferAttribute, BufferGeometry, LineBasicMaterial, PointsMaterial } from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { useViewportState } from "../scene/ViewportStateContext";
import { COLORS } from "../helpers/colors";
import { FACE_CONTOUR_GROUPS } from "../helpers/face-contours";
import { useKeypointsSource, type KeypointsFrame } from "../KeypointsSourceContext";
import { finitePoint, sameNames } from "./prepared-models";

import {KeypointPackingWorkspace} from '../keypoint-storage';

/** Face points and contours read the source array through prepared row indices. */
export function FaceRenderer() {
    const {subscribeToKeypoints} = useKeypointsSource();
    const {statsRef} = useViewportState();
    const {invalidate} = useThree();
    const packingWorkspace = useMemo(() => new KeypointPackingWorkspace(), []);
    const frameRef = useRef<KeypointsFrame | null>(null);
    const namesRef = useRef<readonly string[] | undefined>(undefined);
    const rowsRef = useRef(new Int32Array());
    const contoursRef = useRef(new Int32Array());
    const dirtyRef = useRef(false);
    const dotGeo = useMemo(() => {
        const g = new BufferGeometry(); g.setAttribute("position", new BufferAttribute(new Float32Array(512 * 3).fill(1e5), 3)); return g;
    }, []);
    const lineGeo = useMemo(() => {
        const g = new BufferGeometry();
        const count = FACE_CONTOUR_GROUPS.reduce((sum, group) => sum + group.connections.length, 0);
        g.setAttribute("position", new BufferAttribute(new Float32Array(count * 6).fill(1e5), 3)); return g;
    }, []);
    const dotMat = useMemo(() => new PointsMaterial({color: COLORS.face, size: 2, sizeAttenuation: false}), []);
    const lineMat = useMemo(() => new LineBasicMaterial({color: COLORS.face, transparent: true, opacity: 0.7}), []);
    useEffect(() => () => {dotGeo.dispose(); lineGeo.dispose(); dotMat.dispose(); lineMat.dispose();}, [dotGeo, lineGeo, dotMat, lineMat]);
    useEffect(() => subscribeToKeypoints(frame => {frameRef.current = frame; dirtyRef.current = true; invalidate();}), [subscribeToKeypoints, invalidate]);
    useFrame(() => {
        const frame = frameRef.current;
        if (!frame || !dirtyRef.current) return;
        if (!sameNames(namesRef.current, frame.pointNames)) {
            namesRef.current = frame.pointNames;
            const indices = new Map(frame.pointNames.map((name, index) => [name, index]));
            rowsRef.current = Int32Array.from(frame.pointNames.flatMap((name, index) => /^face[._]/.test(name) ? [index] : []));
            contoursRef.current = Int32Array.from(FACE_CONTOUR_GROUPS.flatMap(group => group.connections.flatMap(([a, b]) => {
                const start = indices.get(`${group.prefix}_${a}`), end = indices.get(`${group.prefix}_${b}`);
                return start !== undefined && end !== undefined ? [start, end] : [];
            })));
            lineGeo.setDrawRange(0, contoursRef.current.length);
            if (rowsRef.current.length > dotGeo.attributes.position.count) {
                dotGeo.dispose();
                dotGeo.setAttribute("position", new BufferAttribute(new Float32Array(rowsRef.current.length * 3), 3));
            }
            dotGeo.setDrawRange(0, rowsRef.current.length);
        }
        const data = packingWorkspace.packFrame(frame), dots = dotGeo.attributes.position.array as Float32Array;
        let count = 0;
        for (let i = 0; i < rowsRef.current.length; i++) {
            const offset = rowsRef.current[i] * 3, base = i * 3;
            if (finitePoint(data, offset)) {
                dots[base] = data[offset]; dots[base + 1] = data[offset + 1]; dots[base + 2] = data[offset + 2]; count++;
            } else dots.fill(1e5, base, base + 3);
        }
        const lines = lineGeo.attributes.position.array as Float32Array;
        for (let i = 0; i < contoursRef.current.length / 2; i++) {
            const a = contoursRef.current[i * 2] * 3, b = contoursRef.current[i * 2 + 1] * 3, base = i * 6;
            if (finitePoint(data, a) && finitePoint(data, b)) {
                lines[base] = data[a]; lines[base + 1] = data[a + 1]; lines[base + 2] = data[a + 2];
                lines[base + 3] = data[b]; lines[base + 4] = data[b + 1]; lines[base + 5] = data[b + 2];
            } else lines.fill(1e5, base, base + 6);
        }
        dotGeo.attributes.position.needsUpdate = true;
        if (contoursRef.current.length) lineGeo.attributes.position.needsUpdate = true;
        dirtyRef.current = false; statsRef.current.face = count;
    });
    return <><points geometry={dotGeo} material={dotMat} frustumCulled={false}/><lineSegments geometry={lineGeo} material={lineMat} frustumCulled={false}/></>;
}
