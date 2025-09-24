import React from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";

const ThreeDScene: React.FC = () => {
  return (
    <Canvas
      camera={{ position: [3, 3, 3], fov: 60 }}
      style={{ background: "#1e1e1e" }}
    >
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 5, 5]} intensity={1} />

      {/* Example cube */}
      <mesh rotation={[0.4, 0.2, 0]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color="orange" />
      </mesh>

      {/* Grid */}
      <Grid
        args={[10, 10]}
        cellSize={1}
        cellColor="#555"
        sectionColor="#888"
        infiniteGrid
      />

      {/* Orbit Controls */}
      <OrbitControls
        enableDamping
        minPolarAngle={Math.PI / 2}
        maxPolarAngle={Math.PI / 2}
      />
    </Canvas>
  );
};

export default ThreeDScene;
