import {useEffect, useMemo, useRef} from "react";
import {Mesh, SphereGeometry, MeshBasicMaterial, Vector2} from "three";
import {Line2, LineGeometry, LineMaterial} from "three-stdlib";
import {useFrame, useThree} from "@react-three/fiber";
import {useViewportState} from "@/components/viewport3d/scene/ViewportStateContext";
import {workerDataStore} from "@/components/viewport3d/WorkerDataStore";
import type {Point3d} from "@/components/viewport3d";

// Effective radius = 50 × 0.50 = 25 world units — softball-sized,
// ~4× larger than body keypoints (50 × 0.12 = 6).
const COM_SCALE = 0.50;
const COM_PROJECTION_SCALE = COM_SCALE * 0.25; // quarter radius
const COM_COLOR = "#44ff44"; // bright green
const COM_COLOR_NUM = 0x44ff44; // LineMaterial needs a number

// XCoM (Hof 2008) — extrapolated center of mass on the ground plane.
// Amber/orange to distinguish from the green CoM family.
const XCOM_COLOR = "#ffaa00";
const XCOM_COLOR_NUM = 0xffaa00;

/**
 * Renders CoM sphere, vertical projection dot, CoM→projection connection
 * line, XCoM sphere, and VP→XCoM connection line. Each sub-element is
 * individually gated by visibility.centerOfMass{Sphere,Projection,
 * Connection,Xcom,XcomConnection}.
 */
export function CenterOfMassRenderer() {
    const { visibility, statsRef } = useViewportState();
    const { invalidate, size } = useThree();

    const sphereRef = useRef<Mesh>(null);
    const projectionRef = useRef<Mesh>(null);
    const lineRef = useRef<Line2>(null);
    const xcomRef = useRef<Mesh>(null);
    const xcomLineRef = useRef<Line2>(null);
    const comRef = useRef<Point3d | null>(null);
    const xcomPosRef = useRef<Point3d | null>(null);

    const sphereGeo = useMemo(() => new SphereGeometry(50, 16, 12), []);
    const projectionGeo = useMemo(() => new SphereGeometry(50, 8, 6), []);
    const xcomGeo = useMemo(() => new SphereGeometry(50, 8, 6), []);
    const sphereMat = useMemo(() => new MeshBasicMaterial({color: COM_COLOR}), []);
    const projectionMat = useMemo(() => new MeshBasicMaterial({color: COM_COLOR, transparent: true, opacity: 0.7}), []);
    const xcomMat = useMemo(() => new MeshBasicMaterial({color: XCOM_COLOR, transparent: true, opacity: 0.85}), []);

    // Fat dashed line from CoM to vertical projection
    const lineGeo = useMemo(() => new LineGeometry(), []);
    const lineMat = useMemo(() => new LineMaterial({
        color: COM_COLOR_NUM,
        linewidth: 2,
        dashed: true,
        dashSize: 10,
        gapSize: 20,
        transparent: true,
        opacity: 0.6,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);
    const lineObj = useMemo(() => new Line2(lineGeo, lineMat), [lineGeo, lineMat]);

    // Solid line from vertical projection to XCoM
    const xcomLineGeo = useMemo(() => new LineGeometry(), []);
    const xcomLineMat = useMemo(() => new LineMaterial({
        color: XCOM_COLOR_NUM,
        linewidth: 2,
        transparent: true,
        opacity: 0.7,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);
    const xcomLineObj = useMemo(() => new Line2(xcomLineGeo, xcomLineMat), [xcomLineGeo, xcomLineMat]);

    useEffect(() => () => {
        sphereGeo.dispose();
        projectionGeo.dispose();
        xcomGeo.dispose();
        sphereMat.dispose();
        projectionMat.dispose();
        xcomMat.dispose();
        lineGeo.dispose();
        lineMat.dispose();
        xcomLineGeo.dispose();
        xcomLineMat.dispose();
    }, [sphereGeo, projectionGeo, xcomGeo, sphereMat, projectionMat, xcomMat, lineGeo, lineMat, xcomLineGeo, xcomLineMat]);

    useEffect(() => {
        const unsubCom = workerDataStore.subscribeToCenterOfMass((point) => {
            comRef.current = point;
            invalidate();
        });
        const unsubXcom = workerDataStore.subscribeToXcom((point) => {
            xcomPosRef.current = point;
            invalidate();
        });
        return () => { unsubCom(); unsubXcom(); };
    }, [invalidate]);

    useFrame(() => {
        const sphere = sphereRef.current;
        const projection = projectionRef.current;
        const line = lineRef.current;
        const xcomMesh = xcomRef.current;
        const xcomLine = xcomLineRef.current;
        const com = comRef.current;
        const xcom = xcomPosRef.current;
        const hasCom = com !== null;
        const hasXcom = xcom !== null;

        // CoM sphere
        if (sphere) {
            if (hasCom && visibility.centerOfMassSphere) {
                sphere.position.set(com.x, com.y, com.z);
                sphere.scale.setScalar(COM_SCALE);
                sphere.visible = true;
            } else {
                sphere.visible = false;
            }
        }

        // Vertical projection dot (on ground plane)
        if (projection) {
            if (hasCom && visibility.centerOfMassProjection) {
                projection.position.set(com.x, com.y, 0);
                projection.scale.setScalar(COM_PROJECTION_SCALE);
                projection.visible = true;
            } else {
                projection.visible = false;
            }
        }

        // CoM → vertical projection dashed line
        if (line) {
            if (hasCom && visibility.centerOfMassConnection) {
                lineGeo.setPositions([com.x, com.y, com.z, com.x, com.y, 0]);
                line.visible = true;
            } else {
                line.visible = false;
            }
        }

        // XCoM sphere (on ground plane, amber)
        if (xcomMesh) {
            if (hasXcom && visibility.centerOfMassXcom) {
                xcomMesh.position.set(xcom.x, xcom.y, 0);
                xcomMesh.scale.setScalar(COM_PROJECTION_SCALE);
                xcomMesh.visible = true;
            } else {
                xcomMesh.visible = false;
            }
        }

        // VP → XCoM connection line (solid, amber)
        if (xcomLine) {
            if (hasCom && hasXcom && visibility.centerOfMassXcomConnection) {
                xcomLineGeo.setPositions([com.x, com.y, 0, xcom.x, xcom.y, 0]);
                xcomLine.visible = true;
            } else {
                xcomLine.visible = false;
            }
        }

        statsRef.current.centerOfMass = hasCom ? 1 : 0;
    });

    return (
        <>
            <mesh ref={sphereRef} geometry={sphereGeo} material={sphereMat} frustumCulled={false} />
            <mesh ref={projectionRef} geometry={projectionGeo} material={projectionMat} frustumCulled={false} />
            <primitive object={lineObj} ref={lineRef} />
            <mesh ref={xcomRef} geometry={xcomGeo} material={xcomMat} frustumCulled={false} />
            <primitive object={xcomLineObj} ref={xcomLineRef} />
        </>
    );
}
