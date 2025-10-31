/*
 * ::::: by  Pooya Deperson 2025  <pooyadeperson@gmail.com> :::::
 *
 *  React Component: ThreeDScene
 *
 *  PURPOSE:
 *     Renders an interactive 3D scene using React Three Fiber (R3F),
 *     displaying the "freemocap-skelly.glb" model with lighting,
 *     grid reference, and camera orbit controls.
 *
 *  FUNCTIONAL DETAILS:
 *     - Uses React `Suspense` for async model loading.
 *     - Displays a temporary loader overlay (`.skeleton-loader-overlay`)
 *       while the 3D model is being fetched and initialized.
 *     - Initializes a perspective camera positioned at `[2.17, 0.97, 2.91]`
 *       and rotated slightly for a natural viewing angle.
 *     - `OrbitControls` allows intuitive mouse-based orbiting around the model.
 *     - `Grid` adds visual reference lines to orient the 3D space.
 *     - Prevents SSR (Server-Side Rendering) errors by rendering only
 *       after the component has mounted (`isClient` check).
 *
 */

import React, { useState, useEffect, Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, useGLTF } from "@react-three/drei";


const SkellyModel: React.FC<{ onLoaded: () => void }> = ({ onLoaded }) => {
  const { scene } = useGLTF("/3d-asset/freemocap-skelly.glb");
  useEffect(() => {
    onLoaded();
  }, [onLoaded]);
  return <primitive object={scene} scale={1} position={[0, 0, 0]} />;
};

const ThreeDScene: React.FC = () => {
  const [isClient, setIsClient] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) return null; // Prevent SSR crash

  const cameraPosition: [number, number, number] = [2.17, 0.97, 2.91];
  const cameraRotation: [number, number, number] = [-0.11, 0.64, 0.07];

  return (
    <div style={{ position: "relative", width: "100%", height: "100vh" }}>
      {/* Inject loader CSS */}
      {/* <style>{loaderStyles}</style> */}

      {/* Loader Overlay */}
      {loading && <div className="skeleton-loader-overlay" style={{ opacity: loading ? 1 : 0 }} />}

      <Canvas
        camera={{ position: cameraPosition, fov: 60, rotation: cameraRotation }}
        style={{ background: "#1e1e1e" }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 5, 5]} intensity={1} />

        <Suspense fallback={null}>
          <SkellyModel onLoaded={() => setLoading(false)} />
        </Suspense>

        <Grid
          args={[10, 10]}
          cellSize={1}
          cellColor="#555"
          sectionColor="#888"
          infiniteGrid
        />

        <OrbitControls
          enableDamping
          minPolarAngle={0}
          maxPolarAngle={Math.PI / 2}
          target={[0, 0.5, 0]}
        />
      </Canvas>
    </div>
  );
};

export default ThreeDScene;