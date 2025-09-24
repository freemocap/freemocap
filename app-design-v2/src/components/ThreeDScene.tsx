import React from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, useGLTF } from "@react-three/drei";
// import CameraLogger from "./CameraLogger"; // correct relative path

const SkellyModel: React.FC = () => {
  const { scene } = useGLTF("/3d-asset/freemocap-skelly.glb");
  return <primitive object={scene} scale={1} position={[0, 0, 0]} />;
};

const ThreeDScene: React.FC = () => {
  // Use your logged camera values here
  const cameraPosition: [number, number, number] = [2.17, 0.97, 2.91];
  const cameraRotation: [number, number, number] = [-0.11, 0.64, 0.07];

  
  return (
    <Canvas
      camera={{ position: cameraPosition, fov: 60, rotation: cameraRotation }}
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
      <OrbitControls
  enableDamping
  minPolarAngle={0}
  maxPolarAngle={Math.PI / 2}
  target={[0, 0.5, 0]} // make it look at the same point your camera was looking at
/>
      {/* <CameraLogger /> */}
    </Canvas>
  );
};

export default ThreeDScene;
