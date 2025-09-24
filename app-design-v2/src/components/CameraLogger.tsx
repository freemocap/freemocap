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