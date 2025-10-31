/*
 * ::::: by  Pooya Deperson 2025  <pooyadeperson@gmail.com> :::::
 *
 * 📁 React Component: CameraLogger
 *
 * 📘 PURPOSE:
 *     A lightweight debug tool that logs the camera’s position and rotation
 *     values in real-time within a Three.js (React Three Fiber) scene.
 *
 * ⚙️ HOW TO USE (React Three Fiber):
 *     1. Import and add this component *inside your R3F Canvas*.
 *
 *        ```jsx
 *        import { Canvas } from "@react-three/fiber";
 *        import CameraLogger from "@/components/debug/CameraLogger";
 *
 *        function Scene() {
 *          return (
 *            <Canvas>
 *              { Your 3D scene objects here }
 *              <CameraLogger /> { Logs camera movement }
 *            </Canvas>
 *          );
 *        }
 *       
 *
 *       FEATURES:
 *      Tracks camera position (`x, y, z`) and rotation (`x, y, z`).
 *      Logs only when camera values change — avoids console spam.
 *      Lightweight and non-intrusive (returns `null` – no visual output).
 *
 */


import { useFrame, useThree } from "@react-three/fiber";
import { useRef } from "react";

const CameraLogger: React.FC = () => {
  const { camera } = useThree();
  const prev = useRef({ pos: [0,0,0], rot: [0,0,0] });

  useFrame(() => {
    const pos = camera.position.toArray();
    const rot = [
      camera.rotation.x,
      camera.rotation.y,
      camera.rotation.z,
    ];

    // Only log when it changes to reduce spam
    if (
      pos.some((v, i) => v !== prev.current.pos[i]) ||
      rot.some((v, i) => v !== prev.current.rot[i])
    ) {
      console.log(
        `position: [${pos.map(v => v.toFixed(2)).join(", ")}], rotation: [${rot.map(v => v.toFixed(2)).join(", ")}]`
      );
      prev.current.pos = pos;
      prev.current.rot = rot;
    }
  });

  return null;
};

export default CameraLogger;