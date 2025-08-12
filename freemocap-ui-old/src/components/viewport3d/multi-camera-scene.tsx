"use client"

import { useRef, useState, useMemo } from "react"
import { Canvas, useFrame, useThree } from "@react-three/fiber"
import { PerspectiveCamera, OrbitControls } from "@react-three/drei"
import * as THREE from "three"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const CameraObject = ({ position, lookAt }) => {
  const mesh = useRef()

  useFrame(() => {
    mesh.current.lookAt(lookAt)
  })

  return (
    <mesh ref={mesh} position={position}>
      <boxGeometry args={[0.2, 0.2, 0.3]} />
      <meshStandardMaterial color="gray" />
    </mesh>
  )
}

const Scene = ({ selectedCamera, setSelectedCamera }) => {
  const { scene, camera } = useThree()
  const insetRef = useRef()

  const cameras = useMemo(
    () => [
      new THREE.PerspectiveCamera(75, 1, 0.1, 1000),
      new THREE.PerspectiveCamera(75, 1, 0.1, 1000),
      new THREE.PerspectiveCamera(75, 1, 0.1, 1000),
      new THREE.PerspectiveCamera(75, 1, 0.1, 1000),
    ],
    [],
  )

  const cameraPositions = [
    [3, 1, 3],
    [-3, 1, 3],
    [3, 1, -3],
    [-3, 1, -3],
  ]

  useFrame(({ gl }) => {
    gl.autoClear = true
    gl.setViewport(0, 0, gl.domElement.width, gl.domElement.height)
    gl.render(scene, camera)

    gl.autoClear = false
    gl.clearDepth()
    gl.setScissorTest(true)

    const insetWidth = gl.domElement.width / 4
    const insetHeight = gl.domElement.height / 4

    gl.setScissor(10, gl.domElement.height - insetHeight - 10, insetWidth, insetHeight)
    gl.setViewport(10, gl.domElement.height - insetHeight - 10, insetWidth, insetHeight)

    gl.render(scene, cameras[selectedCamera])

    gl.setScissorTest(false)
  })

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />

      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color="hotpink" />
      </mesh>

      {cameras.map((_, index) => (
        <CameraObject key={index} position={cameraPositions[index]} lookAt={[0, 0, 0]} />
      ))}

      {cameras.map((cam, index) => (
        <PerspectiveCamera
          key={index}
          makeDefault={index === selectedCamera}
          position={cameraPositions[index]}
          fov={75}
          aspect={1}
          near={0.1}
          far={1000}
        />
      ))}

      <OrbitControls />
    </>
  )
}

export default function Component() {
  const [selectedCamera, setSelectedCamera] = useState(0)

  return (
    <div className="w-full h-screen relative">
      <Canvas>
        <Scene selectedCamera={selectedCamera} setSelectedCamera={setSelectedCamera} />
      </Canvas>
      <div className="absolute top-4 right-4">
        <Select value={selectedCamera.toString()} onValueChange={(value) => setSelectedCamera(Number.parseInt(value))}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select a camera" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">Camera 1</SelectItem>
            <SelectItem value="1">Camera 2</SelectItem>
            <SelectItem value="2">Camera 3</SelectItem>
            <SelectItem value="3">Camera 4</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

