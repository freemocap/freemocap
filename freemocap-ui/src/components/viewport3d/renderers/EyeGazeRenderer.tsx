/**
 * EyeGazeRenderer — Renders Pupil Labs 3D eyeball spheres and gaze vectors.
 *
 * Position:
 *   - Right eye (eye_id=0): origin [0, 0, 0]
 *   - Left eye  (eye_id=1): offset +100mm in Y [0, 100, 0]
 *
 * Each eye renders:
 *   1. A white sphere (12mm radius) representing the eyeball
 *   2. A red semi-transparent cylinder (1000mm long, 1.5mm radius) representing
 *      the gaze direction, oriented along the ``circle_normal`` from Pupil Capture.
 *
 * The gaze cylinder uses a quaternion rotation from local +Y to the normal
 * direction (``setFromUnitVectors``), positioned at the midpoint of the
 * gaze line (eye_center + normal * 500).
 */
import { useEffect, useMemo, useRef } from "react";
import {
    CylinderGeometry,
    Group,
    Mesh,
    MeshStandardMaterial,
    Quaternion,
    SphereGeometry,
    Vector3,
} from "three";
import { useFrame } from "@react-three/fiber";
import { workerDataStore } from "../WorkerDataStore";
import type { PupilFramePayload } from "../helpers/pupil-types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Eyeball sphere radius in mm (matches human eye ~12mm). */
const EYEBALL_RADIUS_MM = 12;
/** Gaze vector cylinder length in mm (1 meter). */
const GAZE_LENGTH_MM = 1000;
/** Gaze vector cylinder radius in mm. */
const GAZE_RADIUS_MM = 1.5;
/** Y-axis offset for left eye in mm. */
const LEFT_EYE_Y_OFFSET_MM = 100;

/** Right eye world position (origin). */
const RIGHT_EYE_POS = new Vector3(0, 0, 0);
/** Left eye world position. */
const LEFT_EYE_POS = new Vector3(0, LEFT_EYE_Y_OFFSET_MM, 0);

/** Reference up vector for gaze orientation (geometry-aligned cylinder). */
const Y_AXIS = new Vector3(0, 1, 0);

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EyeGazeRenderer() {
    // --- Refs for direct manipulation in useFrame ---
    const rightEyeRef = useRef<Mesh>(null);
    const leftEyeRef = useRef<Mesh>(null);
    const rightGazeRef = useRef<Mesh>(null);
    const leftGazeRef = useRef<Mesh>(null);

    /** Latest pupil frame received from the channel. */
    const latestRef = useRef<PupilFramePayload | null>(null);

    // --- Geometries (shared, immutable) ---
    const sphereGeo = useMemo(
        () => new SphereGeometry(EYEBALL_RADIUS_MM, 16, 12),
        [],
    );
    const cylinderGeo = useMemo(
        () => new CylinderGeometry(GAZE_RADIUS_MM, GAZE_RADIUS_MM, GAZE_LENGTH_MM, 6),
        [],
    );

    // --- Materials ---
    const rightEyeMat = useMemo(
        () => new MeshStandardMaterial({ color: "#ffffff", roughness: 0.3 }),
        [],
    );
    const leftEyeMat = useMemo(
        () => new MeshStandardMaterial({ color: "#f0f0f0", roughness: 0.4 }),
        [],
    );
    const gazeMat = useMemo(
        () =>
            new MeshStandardMaterial({
                color: "#ff4444",
                roughness: 0.5,
                transparent: true,
                opacity: 0.8,
            }),
        [],
    );

    // --- Cleanup ---
    useEffect(() => {
        return () => {
            sphereGeo.dispose();
            cylinderGeo.dispose();
            rightEyeMat.dispose();
            leftEyeMat.dispose();
            gazeMat.dispose();
        };
    }, [sphereGeo, cylinderGeo, rightEyeMat, leftEyeMat, gazeMat]);

    // --- Subscribe to pupil data channel ---
    useEffect(() => {
        return workerDataStore.subscribeToPupilData((data) => {
            latestRef.current = data;
        });
    }, []);

    // --- Per-frame update ---
    useFrame(() => {
        const pupilFrame = latestRef.current;
        if (!pupilFrame) return;

        const rightEye = rightEyeRef.current;
        const leftEye = leftEyeRef.current;
        const rightGaze = rightGazeRef.current;
        const leftGaze = leftGazeRef.current;

        // Hide everything by default, show only when data is present
        let rightVisible = false;
        let leftVisible = false;

        for (const eyeball of pupilFrame.eyeballs) {
            const isLeft = eyeball.eye_id === 1;
            const eyeMesh = isLeft ? leftEye : rightEye;
            const gazeMesh = isLeft ? leftGaze : rightGaze;
            const eyePos = isLeft ? LEFT_EYE_POS : RIGHT_EYE_POS;

            if (!eyeMesh || !gazeMesh) continue;

            // Position the eyeball sphere
            eyeMesh.position.copy(eyePos);
            eyeMesh.visible = true;

            if (isLeft) leftVisible = true;
            else rightVisible = true;

            // Compute gaze direction from circle_normal
            const normal = new Vector3(
                eyeball.circle_normal_x,
                eyeball.circle_normal_y,
                eyeball.circle_normal_z,
            ).normalize();

            // Position gaze cylinder at the midpoint of the gaze line
            gazeMesh.position.set(
                eyePos.x + normal.x * (GAZE_LENGTH_MM / 2),
                eyePos.y + normal.y * (GAZE_LENGTH_MM / 2),
                eyePos.z + normal.z * (GAZE_LENGTH_MM / 2),
            );

            // Orient gaze cylinder from Y-up to the normal direction
            gazeMesh.quaternion.setFromUnitVectors(Y_AXIS, normal);
            gazeMesh.visible = true;
        }

        // Hide eyes that have no data in this frame
        if (rightEye && !rightVisible) rightEye.visible = false;
        if (leftEye && !leftVisible) leftEye.visible = false;
        if (rightGaze && !rightVisible) rightGaze.visible = false;
        if (leftGaze && !leftVisible) leftGaze.visible = false;
    });

    return (
        <group name="eye-gaze-group">
            {/* Right eye (origin) */}
            <mesh ref={rightEyeRef} geometry={sphereGeo} material={rightEyeMat} visible={false} />
            <mesh ref={rightGazeRef} geometry={cylinderGeo} material={gazeMat} visible={false} />

            {/* Left eye (+100mm Y) */}
            <mesh ref={leftEyeRef} geometry={sphereGeo} material={leftEyeMat} visible={false} />
            <mesh ref={leftGazeRef} geometry={cylinderGeo} material={gazeMat} visible={false} />
        </group>
    );
}
