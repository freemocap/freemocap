import {Panel, PanelGroup, PanelResizeHandle} from 'react-resizable-panels';
import ModalWindowControls from '@/components/ui-components/ModalWindowControls';
import {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Matrix4} from 'three';
import ButtonSm from '@/components/ui-components/ButtonSm';

import FormalismCard from './formalism-card';
import './transform-editor.css';
import TransformPreview from './transform-preview';
import {TransformRepresentation} from './reference-transform';

export default function TransformEditor({onClose}: {onClose: () => void}) {
    const [matrix, setMatrix] = useState(() => new Matrix4());
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
                        <FormalismCard title="Position" help="Translation of the custom origin. These same values occupy the last column of the matrix." representation={TransformRepresentation.Euler} indices={[0, 1, 2]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Euler · XYZ" help="Intrinsic XYZ rotations in degrees. Near ±90° Y, equivalent angle values may jump: the orientation itself remains continuous." representation={TransformRepresentation.Euler} indices={[3, 4, 5]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Quaternion · WXYZ" help="Four components describe one rotation. Edits are normalized to unit length; a zero quaternion is rejected. q and −q describe the same orientation." representation={TransformRepresentation.Quaternion} indices={[3, 4, 5, 6]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Axis–angle" help="A unit direction and an angle in degrees. Axis edits are normalized; a zero axis is rejected. The axis is arbitrary at zero rotation." representation={TransformRepresentation.AxisAngle} indices={[3, 4, 5, 6]} matrix={matrix} onChange={setMatrix}/>
                        <FormalismCard title="Transform · 4×4" help="Column-vector convention: p′ = R p + t. Translation is in millimetres. The rotation block must stay orthonormal with determinant +1; scaling, shear and reflection are rejected. Use the rotation controls to change coupled matrix entries together." representation={TransformRepresentation.Matrix} indices={Array.from({length: 16}, (_, index) => index)} matrix={matrix} onChange={setMatrix}/>
                    </div></Panel></PanelGroup>
                <div className="transform-footer flex gap-2 justify-content-space-between">
                    <ButtonSm className="transform-action" text="Reset to identity" onClick={() => {const identity = new Matrix4(); setMatrix(identity);}}/>
                    <ButtonSm className="transform-action" text="Close" onClick={onClose}/>
                </div>
            </div>
        </div>
    </div>, document.body);
}








