import {useEffect, useMemo, useRef} from 'react';
import {BufferAttribute, BufferGeometry, LineBasicMaterial, PointsMaterial, type Points, type LineSegments} from 'three';
import {useFrame, useThree} from '@react-three/fiber';
import {useViewportState} from '../scene/ViewportStateContext';
import {COLORS} from '../helpers/colors';
import {useKeypointsSource, useModelDefinitionsById, type KeypointsFrame} from '../KeypointsSourceContext';
import {sameNames} from './prepared-models';
import {KeypointPackingWorkspace} from '../keypoint-storage';
import {prepareFace, writeFace, type PreparedFace} from './prepared-face';

/** One points batch and one line batch, shared by live and recorded sources. */
export function FaceRenderer() {
    const {subscribeToKeypoints} = useKeypointsSource();
    const definitions = useModelDefinitionsById();
    const definitionsRef = useRef(definitions.current);
    const {statsRef, visibility} = useViewportState();
    const {invalidate} = useThree();
    const workspace = useMemo(() => new KeypointPackingWorkspace(), []);
    const frameRef = useRef<KeypointsFrame | null>(null);
    const namesRef = useRef<readonly string[] | undefined>(undefined);
    const prepared = useRef<PreparedFace>({points: new Int32Array(), edges: new Int32Array()});
    const dirty = useRef(true);
    const dotsRef = useRef<Points>(null);
    const linesRef = useRef<LineSegments>(null);
    const dotGeo = useMemo(() => new BufferGeometry(), []);
    const lineGeo = useMemo(() => new BufferGeometry(), []);
    const dotMat = useMemo(() => new PointsMaterial({color: COLORS.face, size: 2, sizeAttenuation: false}), []);
    const lineMat = useMemo(() => new LineBasicMaterial({color: COLORS.face, transparent: true, opacity: .7}), []);
    useEffect(() => () => {
        dotGeo.dispose(); lineGeo.dispose(); dotMat.dispose(); lineMat.dispose();
        statsRef.current.face = 0; statsRef.current.faceConnections = 0;
    }, [dotGeo, lineGeo, dotMat, lineMat, statsRef]);
    useEffect(() => subscribeToKeypoints(frame => {frameRef.current = frame; dirty.current = true; invalidate();}), [subscribeToKeypoints, invalidate]);
    useEffect(() => {dirty.current = true; invalidate();}, [visibility.face, visibility.faceConnections, invalidate]);
    useFrame(() => {
        const frame = frameRef.current;
        if (!frame) return;
        if (!sameNames(namesRef.current, frame.pointNames) || definitionsRef.current !== definitions.current) {
            namesRef.current = frame.pointNames; definitionsRef.current = definitions.current;
            prepared.current = prepareFace(frame.pointNames, definitions.current.values());
            // Release replaced GPU attributes only when layout capacity changes.
            for (const [geometry, count] of [[dotGeo, prepared.current.points.length], [lineGeo, prepared.current.edges.length]] as const) {
                if (geometry.attributes.position?.count !== Math.max(1, count)) {
                    geometry.dispose();
                    geometry.setAttribute('position', new BufferAttribute(new Float32Array(Math.max(1, count) * 3), 3));
                }
                geometry.setDrawRange(0, 0);
            }
            dirty.current = true;
        }
        if (!dirty.current) return;
        const data = workspace.packFrame(frame);
        const dots = visibility.face ? writeFace(data, prepared.current.points, dotGeo.attributes.position.array as Float32Array, false) : 0;
        const lines = visibility.faceConnections ? writeFace(data, prepared.current.edges, lineGeo.attributes.position.array as Float32Array, true) : 0;
        dotGeo.setDrawRange(0, dots); lineGeo.setDrawRange(0, lines * 2);
        if (dotsRef.current) dotsRef.current.visible = dots > 0;
        if (linesRef.current) linesRef.current.visible = lines > 0;
        if (dots) dotGeo.attributes.position.needsUpdate = true;
        if (lines) lineGeo.attributes.position.needsUpdate = true;
        statsRef.current.face = dots; statsRef.current.faceConnections = lines;
        dirty.current = false;
    });
    return <><points ref={dotsRef} visible={false} geometry={dotGeo} material={dotMat} frustumCulled={false}/>
        <lineSegments ref={linesRef} visible={false} geometry={lineGeo} material={lineMat} frustumCulled={false}/></>;
}
