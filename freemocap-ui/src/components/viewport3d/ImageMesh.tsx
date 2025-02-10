import React, {useEffect, useRef} from 'react';
import {useLoader, useThree} from '@react-three/fiber';
import * as THREE from 'three';

interface ImageMeshProps {
    imageUrl: string;
    position: [number, number, number];
}

export const ImageMesh: React.FC<ImageMeshProps> = ({imageUrl, position}) => {
    const texture = useLoader(THREE.TextureLoader, imageUrl);
    const meshRef = useRef<THREE.Mesh>(null);
    const cameraRef = useRef<THREE.PerspectiveCamera>(null);
    const {scene} = useThree();

    useEffect(() => {
        if (meshRef.current && cameraRef.current) {
            const mesh = meshRef.current;
            const camera = cameraRef.current;

            // Set camera position and orientation
            camera.position.set(position[0], position[1], position[2] + 3);
            camera.lookAt(mesh.position);

            //Compute image size for far plane alignment
            const imageAspect = texture.image.width / texture.image.height;
            const imageWidth = imageAspect > 1 ? 2 : 2 * imageAspect;
            const imageHeight = imageAspect > 1 ? 2 / imageAspect : 2;

            camera.near = 0.1;
            camera.far = Math.max(imageWidth, imageHeight);
            const helper = new THREE.CameraHelper(camera);
            scene.add(helper);
            meshRef.current.material.map = texture;
            meshRef.current.material.needsUpdate = true;
        }
    }, [texture]);

    return (
        <>
            <mesh ref={meshRef} position={position}>
                <planeGeometry args={[2, 1]}/>
                <meshBasicMaterial/>
            </mesh>
            <perspectiveCamera ref={cameraRef}/>
        </>
    );
};
