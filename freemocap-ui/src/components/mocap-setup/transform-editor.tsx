import {Panel, PanelGroup, PanelResizeHandle} from 'react-resizable-panels';
import ModalWindowControls from '@/components/ui-components/ModalWindowControls';
import {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Matrix4} from 'three';
import ButtonSm from '@/components/ui-components/ButtonSm';

import FormalismCard from './formalism-card';
import './transform-editor.css';
import TransformPreview from './transform-preview';
import {TransformRepresentation, validateRigidTransform} from './reference-transform';

interface TransformEditorProps {
    initialMatrix: Matrix4;
    onAccept: (matrix: Matrix4) => void;
    onClose: () => void;
}

export default function TransformEditor({initialMatrix, onAccept, onClose}: TransformEditorProps) {
    const [matrix, setMatrix] = useState(() => initialMatrix.clone());
    const dialog = useRef<HTMLDivElement>(null);
    useEffect(() => {
        const previous = document.activeElement as HTMLElement | null;
        dialog.current?.focus();
        return () => previous?.focus();
    }, []);
    return createPortal(<div className="pos-fixed inset-0" style={{zIndex: 1000}}
        onKeyDown={event => {
            if (event.key === 'Escape') {event.stopPropagation(); onClose();}
            if (event.key === 'Tab') {
                const nodes = dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input, select');
                if (!nodes?.length) return;
                const first = nodes[0], last = nodes[nodes.length - 1];
                if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {event.preventDefault(); last.focus();}
                else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
            }
        }}>
        <div className="pos-fixed inset-0 bg-surface-overlay" onClick={onClose}/>
        <div ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Custom reference frame"
            className="settings-modal bg-primary border-1 border-black pos-fixed elevated-sharp p-1 flex flex-col br-2"
            style={{width: 'min(1000px, 94vw)', height: 'min(600px, 85vh)'}}>
<ModalWindowControls title="Custom reference frame"/>
            <div className="modal-window-body flex flex-col p-2 gap-2 bg-middark br-1">
                <PanelGroup direction="horizontal" className="transform-editor-layout">
                    <Panel defaultSize={62} minSize={30}>
                    <TransformPreview matrix={matrix} onChange={setMatrix}/>
                    </Panel>
                    <PanelResizeHandle className="transform-panel-divider"/>
                    <Panel defaultSize={38} minSize={25} className="transform-controls-panel">
                    <div className="formalism-cards">
                        <FormalismCard title="Position" help={<><p><strong>Translation</strong> moves the custom origin.</p><p>These values also appear in the <strong>last column</strong> of the matrix.</p></>} representation={TransformRepresentation.Euler} indices={[0, 1, 2]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Euler · XYZ" help={<><p><strong>Intrinsic XYZ</strong> rotations, measured in degrees.</p><p><em>Near ±90° Y:</em> equivalent angles may jump while the orientation stays continuous.</p></>} representation={TransformRepresentation.Euler} indices={[3, 4, 5]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Quaternion · WXYZ" help={<><p><strong>Four components, one rotation.</strong> Edits are normalized to unit length.</p><p>A <strong>zero quaternion</strong> is rejected.</p><p><em>q and −q describe the same orientation.</em></p></>} representation={TransformRepresentation.Quaternion} indices={[3, 4, 5, 6]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Axis–angle" help={<><p><strong>Axis:</strong> a unit direction. Edits are normalized; a zero axis is rejected.</p><p><strong>Angle:</strong> rotation in degrees.</p><p><em>At zero rotation, any axis gives the same result.</em></p></>} representation={TransformRepresentation.AxisAngle} indices={[3, 4, 5, 6]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Transform · 4×4" help={<><p><strong>Column vectors:</strong> <code>p′ = R p + t</code></p><p><strong>Translation:</strong> millimetres in the last column.</p><p><strong>Rotation:</strong> orthonormal, with determinant +1. Scaling, shear and reflection are rejected.</p><p><em>Use the rotation controls to change coupled entries together.</em></p></>} representation={TransformRepresentation.Matrix} indices={Array.from({length: 16}, (_, index) => index)} matrix={matrix} onChange={setMatrix}/>
                    </div></Panel></PanelGroup>
                <div className="transform-footer flex gap-2 justify-content-space-between">
                    <ButtonSm className="transform-action" text="Reset to identity" onClick={() => {const identity = new Matrix4(); setMatrix(identity);}}/>
                    <div className="flex gap-2">
                        <ButtonSm className="transform-action" text="Cancel" onClick={onClose}/>
                        <ButtonSm className="transform-action" textColor="text-white" text="Accept transformation" onClick={() => onAccept(validateRigidTransform(matrix.clone()))}/>
                    </div>
                </div>
            </div>
        </div>
    </div>, document.body);
}











