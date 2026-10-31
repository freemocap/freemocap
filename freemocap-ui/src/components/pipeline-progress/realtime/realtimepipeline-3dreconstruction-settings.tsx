import React, {useEffect, useRef} from 'react';
import {TemporalFilterControls} from '@/components/control-panels/realtime-panel/TemporalFilterControls';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import SkeletonAnchorSetting from '@/components/mocap-setup/skeleton-anchor-setting';

export default function RTPthreeDReconstructionSettings({open, onClose}: {open: boolean; onClose: () => void}) {
    const modalRef = useRef<HTMLDivElement>(null);
    const {pipelineConfig, aggregatorConfig, applyOrUpdatePipelineConfig} = useRealtimePipelineSync();
    useEffect(() => {
        if (!open) return;
        const keyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
        const outsideClick = (event: MouseEvent) => {if (!modalRef.current?.contains(event.target as Node)) onClose();};
        window.addEventListener('keydown', keyDown);
        document.addEventListener('mousedown', outsideClick);
        return () => {window.removeEventListener('keydown', keyDown); document.removeEventListener('mousedown', outsideClick);};
    }, [open, onClose]);
    if (!open) return null;
    return <div ref={modalRef} className="RTP-settings-flyout pos-abs top-5 right-0 border-1 elevated-sharp flex flex-col p-2 bg-dark br-2 gap-1"
        style={{maxHeight: '80vh', overflowY: 'auto', width: 400}}>
        <div className="flex flex-row justify-content-space-between"><strong>Realtime processing</strong>
            <button className="button sm" onClick={onClose}>Close settings</button></div>
        <SkeletonAnchorSetting value={aggregatorConfig.anchor_segment_name} onChange={value => applyOrUpdatePipelineConfig({
            ...pipelineConfig, aggregator_config: {...aggregatorConfig, anchor_segment_name: value},
        })}/>
        <label><input type="checkbox" checked={aggregatorConfig.skeleton_fitting_enabled}
            onChange={event => applyOrUpdatePipelineConfig({...pipelineConfig, aggregator_config: {
                ...aggregatorConfig, skeleton_fitting_enabled: event.target.checked,
            }})}/> Fit skeleton</label>
        <TemporalFilterControls/>
    </div>;
}
