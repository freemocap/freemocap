import React from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, useGLTF } from "@react-three/drei";

const SkellyModel: React.FC = () => {
  const { scene } = useGLTF("/3d-asset/freemocap-skelly.glb");
  return <primitive object={scene} scale={1} position={[0, 0, 0]} />;
};

const ThreeDScene: React.FC = () => {
  return (
    <Canvas
       camera={{ position: [2, 2, 2], fov: 60 }}
      style={{ background: "#1e1e1e" }}
    >
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 5, 5]} intensity={1} />

      {/* GLB Model */}
      <SkellyModel />

      {/* Grid (ground plane) */}
      <Grid
        args={[10, 10]}
        cellSize={1}
        cellColor="#555"
        sectionColor="#888"
        infiniteGrid
      />

      {/* Orbit Controls */}
      <OrbitControls enableDamping minPolarAngle={0} maxPolarAngle={Math.PI / 2} />
    </Canvas>
  );
};

export default ThreeDScene;
