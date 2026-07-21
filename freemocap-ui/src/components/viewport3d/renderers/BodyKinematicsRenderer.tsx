import {useEffect, useMemo, useRef} from "react";
import {Mesh, SphereGeometry, MeshBasicMaterial, Vector2, Vector3, Matrix4} from "three";
import {Line2, LineGeometry, LineMaterial} from "three-stdlib";
import {useFrame, useThree} from "@react-three/fiber";
import {useViewportState} from "@/components/viewport3d/scene/ViewportStateContext";
import {workerDataStore} from "@/components/viewport3d/WorkerDataStore";
import type {BodyKinematics} from "@/components/viewport3d";

// Reaction-mass (inertia) ellipsoid — violet, distinct from the green CoM
// family and the amber XCoM. Translucent + depthWrite off so it ghosts the
// skeleton rather than hiding it.
const ELLIPSOID_COLOR = "#aa66ff";
const ELLIPSOID_OPACITY = 0.18;
// Display gain on the (physical, equimomental) semi-axes, in mm. 1.0 = true size.
const ELLIPSOID_SCALE = 1.0;

// Centroidal Moment Pivot — magenta ground marker. Its gap from the CoP is the
// on-the-floor readout of centroidal angular-momentum rate.
const CMP_COLOR = "#ff44aa";
const CMP_COLOR_NUM = 0xff44aa;
const CMP_SCALE = 0.125; // on a radius-50 sphere -> ~6 world units, like the CoM projection dot

/**
 * Renders the reaction-mass ellipsoid at the CoM (oriented by its principal
 * axes, scaled by its semi-axes) plus the CMP marker and a CoP→CMP line. Each
 * sub-element is gated by visibility.{reactionMassEllipsoid,centroidalMomentPivot}.
 */
export function BodyKinematicsRenderer() {
    const { visibility } = useViewportState();
    const { invalidate, size } = useThree();

    const ellipsoidRef = useRef<Mesh>(null);
    const cmpRef = useRef<Mesh>(null);
    const cmpLineRef = useRef<Line2>(null);
    const bkRef = useRef<BodyKinematics | null>(null);

    const ellipsoidGeo = useMemo(() => new SphereGeometry(1, 24, 16), []);
    const ellipsoidMat = useMemo(() => new MeshBasicMaterial({
        color: ELLIPSOID_COLOR, transparent: true, opacity: ELLIPSOID_OPACITY, depthWrite: false,
    }), []);
    const cmpGeo = useMemo(() => new SphereGeometry(50, 8, 6), []);
    const cmpMat = useMemo(() => new MeshBasicMaterial({color: CMP_COLOR, transparent: true, opacity: 0.9}), []);

    const cmpLineGeo = useMemo(() => new LineGeometry(), []);
    const cmpLineMat = useMemo(() => new LineMaterial({
        color: CMP_COLOR_NUM,
        linewidth: 2,
        transparent: true,
        opacity: 0.7,
        resolution: new Vector2(size.width, size.height),
    }), [size.width, size.height]);
    const cmpLineObj = useMemo(() => new Line2(cmpLineGeo, cmpLineMat), [cmpLineGeo, cmpLineMat]);

    // Reusable math scratch (avoid per-frame allocation).
    const basis = useMemo(() => new Matrix4(), []);
    const axX = useMemo(() => new Vector3(), []);
    const axY = useMemo(() => new Vector3(), []);
    const axZ = useMemo(() => new Vector3(), []);

    useEffect(() => () => {
        ellipsoidGeo.dispose();
        ellipsoidMat.dispose();
        cmpGeo.dispose();
        cmpMat.dispose();
        cmpLineGeo.dispose();
        cmpLineMat.dispose();
    }, [ellipsoidGeo, ellipsoidMat, cmpGeo, cmpMat, cmpLineGeo, cmpLineMat]);

    useEffect(() => {
        return workerDataStore.subscribeToBodyKinematics((bk) => {
            bkRef.current = bk;
            invalidate();
        });
    }, [invalidate]);

    useFrame(() => {
        const bk = bkRef.current;
        const ellipsoid = ellipsoidRef.current;
        const cmpMesh = cmpRef.current;
        const cmpLine = cmpLineRef.current;

        // Reaction-mass ellipsoid at the CoM
        if (ellipsoid) {
            const semi = bk?.ellipsoid_semi_axes ?? null;
            const ax = bk?.ellipsoid_axis_x ?? null;
            const ay = bk?.ellipsoid_axis_y ?? null;
            const az = bk?.ellipsoid_axis_z ?? null;
            if (bk && semi && ax && ay && az && visibility.reactionMassEllipsoid) {
                ellipsoid.position.set(bk.center_of_mass.x, bk.center_of_mass.y, bk.center_of_mass.z);
                axX.set(ax.x, ax.y, ax.z);
                axY.set(ay.x, ay.y, ay.z);
                axZ.set(az.x, az.y, az.z);
                basis.makeBasis(axX, axY, axZ);
                ellipsoid.quaternion.setFromRotationMatrix(basis);
                ellipsoid.scale.set(
                    Math.max(semi.x, 1) * ELLIPSOID_SCALE,
                    Math.max(semi.y, 1) * ELLIPSOID_SCALE,
                    Math.max(semi.z, 1) * ELLIPSOID_SCALE,
                );
                ellipsoid.visible = true;
            } else {
                ellipsoid.visible = false;
            }
        }

        // CMP ground marker
        const cmp = bk?.cmp ?? null;
        const cop = bk?.center_of_pressure ?? null;
        if (cmpMesh) {
            if (cmp && visibility.centroidalMomentPivot) {
                cmpMesh.position.set(cmp.x, cmp.y, 0);
                cmpMesh.scale.setScalar(CMP_SCALE);
                cmpMesh.visible = true;
            } else {
                cmpMesh.visible = false;
            }
        }

        // CoP → CMP line (the angular-momentum-rate readout)
        if (cmpLine) {
            if (cmp && cop && visibility.centroidalMomentPivot) {
                cmpLineGeo.setPositions([cop.x, cop.y, 0, cmp.x, cmp.y, 0]);
                cmpLine.visible = true;
            } else {
                cmpLine.visible = false;
            }
        }
    });

    return (
        <>
            <mesh ref={ellipsoidRef} geometry={ellipsoidGeo} material={ellipsoidMat} frustumCulled={false} />
            <mesh ref={cmpRef} geometry={cmpGeo} material={cmpMat} frustumCulled={false} />
            <primitive object={cmpLineObj} ref={cmpLineRef} />
        </>
    );
}
