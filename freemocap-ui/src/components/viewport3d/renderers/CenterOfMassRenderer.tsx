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

/**
 * Renders COM sphere, vertical projection dot, and COM→projection
 * connection line. Each sub-element is individually gated by
 * visibility.centerOfMass{Sphere,Projection,Connection}.
 */
export function CenterOfMassRenderer() {
    const { visibility, statsRef } = useViewportState();
    const { invalidate, size } = useThree();

    const sphereRef = useRef<Mesh>(null);
    const projectionRef = useRef<Mesh>(null);
    const lineRef = useRef<Line2>(null);
    const comRef = useRef<Point3d | null>(null);

    const sphereGeo = useMemo(() => new SphereGeometry(50, 16, 12), []);
    const projectionGeo = useMemo(() => new SphereGeometry(50, 8, 6), []);
    const sphereMat = useMemo(() => new MeshBasicMaterial({color: COM_COLOR}), []);
    const projectionMat = useMemo(() => new MeshBasicMaterial({color: COM_COLOR, transparent: true, opacity: 0.7}), []);

    // Fat line: Line2 from three-stdlib — supports linewidth on Windows/WebGL
    const lineGeo = useMemo(() => new LineGeometry(), []);
    const lineMat = useMemo(() => new LineMaterial({
        color: COM_COLOR_NUM,
        linewidth: 2, // pixels
        dashed: true,
        dashSize: 10,  // world units
        gapSize: 20,   // world units
        transparent: true,
        opacity: 0.6,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);
    const lineObj = useMemo(() => new Line2(lineGeo, lineMat), [lineGeo, lineMat]);

    useEffect(() => () => {
        sphereGeo.dispose();
        projectionGeo.dispose();
        sphereMat.dispose();
        projectionMat.dispose();
        lineGeo.dispose();
        lineMat.dispose();
    }, [sphereGeo, projectionGeo, sphereMat, projectionMat, lineGeo, lineMat]);

    useEffect(() => {
        return workerDataStore.subscribeToCenterOfMass((point) => {
            comRef.current = point;
            invalidate();
        });
    }, [invalidate]);

    useFrame(() => {
        const sphere = sphereRef.current;
        const projection = projectionRef.current;
        const line = lineRef.current;
        const com = comRef.current;
        const hasCom = com !== null;

        if (sphere) {
            if (hasCom && visibility.centerOfMassSphere) {
                sphere.position.set(com.x, com.y, com.z);
                sphere.scale.setScalar(COM_SCALE);
                sphere.visible = true;
            } else {
                sphere.visible = false;
            }
        }

        if (projection) {
            if (hasCom && visibility.centerOfMassProjection) {
                projection.position.set(com.x, com.y, 0);
                projection.scale.setScalar(COM_PROJECTION_SCALE);
                projection.visible = true;
            } else {
                projection.visible = false;
            }
        }

        if (line) {
            if (hasCom && visibility.centerOfMassConnection) {
                lineGeo.setPositions([com.x, com.y, com.z, com.x, com.y, 0]);
                line.visible = true;
            } else {
                line.visible = false;
            }
        }

        statsRef.current.centerOfMass = hasCom ? 1 : 0;
    });

    return (
        <>
            <mesh ref={sphereRef} geometry={sphereGeo} material={sphereMat} frustumCulled={false} />
            <mesh ref={projectionRef} geometry={projectionGeo} material={projectionMat} frustumCulled={false} />
            <primitive object={lineObj} ref={lineRef} />
        </>
    );
}
