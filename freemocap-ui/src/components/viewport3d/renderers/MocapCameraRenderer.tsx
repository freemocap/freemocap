import { useEffect, useMemo } from "react";
import {
    BufferAttribute,
    BufferGeometry,
    Matrix3,
    Matrix4,
    Quaternion,
    Vector3,
} from "three";
import { useAppSelector } from "@/store";
import {
    CalibrationCameraData,
    selectLoadedCalibration,
} from "@/store/slices/calibration/calibration-slice";
import { useViewportState } from "../scene/ViewportStateContext";

const FRUSTUM_DEPTH_MM = 75;
const BODY_SIZE_MM = 20;
const FRUSTUM_COLOR = "#106995";
const BODY_COLOR = "#2080b0";

interface CameraPose {
    position: Vector3;
    quaternion: Quaternion;
    halfW: number;
    halfH: number;
}

function computePose(cam: CalibrationCameraData): CameraPose | null {
    const wo = cam.world_orientation;
    const wp = cam.world_position;
    if (!wo || wo.length !== 3 || !wp || wp.length !== 3) return null;

    const m3 = new Matrix3().set(
        wo[0][0], wo[0][1], wo[0][2],
        wo[1][0], wo[1][1], wo[1][2],
        wo[2][0], wo[2][1], wo[2][2],
    );
    const m4 = new Matrix4().setFromMatrix3(m3);
    const quaternion = new Quaternion().setFromRotationMatrix(m4);

    const fx = cam.matrix?.[0]?.[0] ?? 1;
    const fy = cam.matrix?.[1]?.[1] ?? fx;
    const [w, h] = cam.size ?? [1280, 720];
    const halfW = FRUSTUM_DEPTH_MM * (w / (2 * fx));
    const halfH = FRUSTUM_DEPTH_MM * (h / (2 * fy));

    return {
        position: new Vector3(wp[0], wp[1], wp[2]),
        quaternion,
        halfW,
        halfH,
    };
}

/**
 * Frustum pyramid in the camera's local frame:
 * apex at (0,0,0), base plane at z = +FRUSTUM_DEPTH_MM (OpenCV optical axis).
 */
function buildFrustumGeometry(halfW: number, halfH: number): BufferGeometry {
    const z = FRUSTUM_DEPTH_MM;
    const c0 = [0, 0, 0];
    const tl = [-halfW, -halfH, z];
    const tr = [ halfW, -halfH, z];
    const br = [ halfW,  halfH, z];
    const bl = [-halfW,  halfH, z];

    const segs: number[][] = [
        c0, tl,  c0, tr,  c0, br,  c0, bl,
        tl, tr,  tr, br,  br, bl,  bl, tl,
    ];
    const positions = new Float32Array(segs.flat());
    const geo = new BufferGeometry();
    geo.setAttribute("position", new BufferAttribute(positions, 3));
    return geo;
}

function MocapCameraInstance({ cam }: { cam: CalibrationCameraData }) {
    const pose = useMemo(() => computePose(cam), [cam]);
    const frustumGeo = useMemo(
        () => (pose ? buildFrustumGeometry(pose.halfW, pose.halfH) : null),
        [pose],
    );

    useEffect(() => {
        return () => { frustumGeo?.dispose(); };
    }, [frustumGeo]);

    if (!pose || !frustumGeo) return null;

    return (
        <group position={pose.position} quaternion={pose.quaternion}>
            <mesh>
                <boxGeometry args={[BODY_SIZE_MM, BODY_SIZE_MM, BODY_SIZE_MM * 0.6]} />
                <meshStandardMaterial color={BODY_COLOR} />
            </mesh>
            <lineSegments geometry={frustumGeo}>
                <lineBasicMaterial color={FRUSTUM_COLOR} />
            </lineSegments>
        </group>
    );
}

export function MocapCameraRenderer() {
    const loaded = useAppSelector(selectLoadedCalibration);
    const { statsRef } = useViewportState();

    useEffect(() => {
        statsRef.current.cameras = loaded?.cameras.length ?? 0;
    }, [loaded, statsRef]);

    if (!loaded || loaded.cameras.length === 0) return null;

    return (
        <>
            {loaded.cameras.map((cam) => (
                <MocapCameraInstance key={cam.id} cam={cam} />
            ))}
        </>
    );
}
