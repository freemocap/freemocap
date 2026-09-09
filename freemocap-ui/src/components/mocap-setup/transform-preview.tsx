import {Canvas} from '@react-three/fiber';
import {Html, Line, OrbitControls} from '@react-three/drei';
import {Group, Matrix4, Vector3} from 'three';
import {useLayoutEffect, useMemo, useRef, useState} from 'react';
import ToggleComponent from '@/components/ui-components/ToggleComponent';


import ReferenceGizmo from './reference-gizmo';
import ReferenceFraming from './reference-framing';



export default function TransformPreview({matrix, onChange}: {matrix: Matrix4; onChange: (matrix: Matrix4) => void}) {
    const [normalize, setNormalize] = useState(true);
    const [showAxisLabels, setShowAxisLabels] = useState(true);

    const [dragging, setDragging] = useState(false);
    const dragScale = useRef(1000);
    const controlledFrame = useMemo(() => new Group(), []);
    const millimetersPerUnit = dragging ? dragScale.current : normalize
        ? Math.max(1000, new Vector3().setFromMatrixPosition(matrix).length()) : 1000;
    const preview = matrix.clone();
    const translation = new Vector3().setFromMatrixPosition(matrix).divideScalar(millimetersPerUnit);
    preview.setPosition(translation);
    useLayoutEffect(() => {
        if (dragging) return;
        const display = matrix.clone().setPosition(new Vector3().setFromMatrixPosition(matrix).divideScalar(millimetersPerUnit));
        display.decompose(controlledFrame.position, controlledFrame.quaternion, controlledFrame.scale);
        controlledFrame.updateMatrixWorld(true);
    }, [matrix, millimetersPerUnit, controlledFrame, dragging]);
    const origin = new Vector3().setFromMatrixPosition(preview);
    const radius = Math.max(1.4, origin.length() + 1);
    return <div className="transform-preview bg-secondary br-1 p-1" aria-label="Neutral and transformed coordinate frames">
        <div className="flex justify-content-space-between p-1 text sm text-gray">
            <span>Reference preview</span>
            <span title="Drag to orbit · scroll to zoom. Axis length: 1 m. Z is up.">↔ Orbit · ⊕ Zoom</span>
        </div>
        <div className="transform-preview-canvas">
        <Canvas frameloop="demand" camera={{position: [radius, -radius * 1.4, radius], up: [0, 0, 1], fov: 40, near: .001, far: 100000}}>
            <OrbitControls target={[.25, .25, .25]} makeDefault/>
            <ReferenceFraming x={origin.x} y={origin.y} z={origin.z} dragging={dragging}/>
            <gridHelper args={[3, 12, '#555555', '#333333']} rotation={[Math.PI / 2, 0, 0]}/>
            {(['x', 'y', 'z'] as const).map((axis, index) => {
                const tip: [number, number, number] = [0, 0, 0];
                tip[index] = 1;
                return <group key={axis}>
                    <Line points={[[0, 0, 0], tip]} color="#c2cbd6" lineWidth={2.5} depthTest={false} renderOrder={1}/>
                    {showAxisLabels && <Html position={tip} center style={{pointerEvents: 'none'}}><span className="text sm reference-axis-label reference-axis-label-neutral">{axis}₀</span></Html>}
                </group>;
            })}
            <mesh><sphereGeometry args={[.03, 16, 12]}/><meshBasicMaterial color="#c2cbd6"/></mesh>
            <Line points={[[0, 0, 0], origin]} color="#888888" dashed dashSize={.04} gapSize={.025}/>
            <ReferenceGizmo object={controlledFrame}
                onStart={() => {dragScale.current = millimetersPerUnit; setDragging(true);}}
                onEnd={() => setDragging(false)}
                onChange={() => {
                    controlledFrame.updateMatrix();
                    const result = controlledFrame.matrix.clone();
                    result.setPosition(controlledFrame.position.clone().multiplyScalar(dragScale.current));
                    onChange(result);
                }}/>
            <primitive object={controlledFrame}>
                <axesHelper args={[1]}/>
                {showAxisLabels && (['x̂', 'ŷ', 'ẑ'] as const).map((label, index) => {
                    const tip: [number, number, number] = [0, 0, 0];
                    tip[index] = 1;
                    return <Html key={label} position={tip} center style={{pointerEvents: 'none'}}>
                        <span className="text sm reference-axis-label reference-axis-label-custom">{label}</span>
                    </Html>;
                })}
                <mesh>
                    <sphereGeometry args={[.055, 24, 16]}/>
                    <meshBasicMaterial color="#dddddd"/>
                </mesh>
            </primitive>
        </Canvas>
        </div>
        <div className="reference-preview-toggles">
        <div className="normalization-chip" title="Preview only: distances over 1 m are compressed to keep both frames visible. Transform values are unchanged.">
            <ToggleComponent text="Normalize distances" isToggled={normalize} onToggle={setNormalize}/>
        </div>
        <div className="normalization-chip">
            <ToggleComponent text="Show axis labels" isToggled={showAxisLabels} onToggle={setShowAxisLabels}/>
        </div>
        </div>
    </div>;
}





