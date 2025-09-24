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
      {loading && <div className="loader-overlay" style={{ opacity: loading ? 1 : 0 }} />}

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
