import React, {useEffect, useRef} from 'react';
import {TemporalFilterControls} from '@/components/control-panels/realtime-panel/TemporalFilterControls';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import SkeletonAnchorSetting from '@/components/mocap-setup/skeleton-anchor-setting';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import AnchoredInfo from '@/components/ui-components/AnchoredInfo';
import IconButton from '@/components/ui-components/IconButton';
import './realtime-settings.css';

export const REALTIME_3D_SETTINGS_TITLE = '3D tracking settings';

const OVERVIEW_INFO = {
    title: 'Realtime 3D processing',
    text: <>
        <p>Each processed frame runs: 2D confidence checks → optional image smoothing → triangulation → velocity
            rejection → optional spatial smoothing → timed gap recovery → skeleton fitting and continuity.</p>
        <p>Skeleton settings apply immediately. Filter settings apply together when you submit them, and the
            processing worker confirms them on the next processed frame.</p>
    </>,
};

const SKELETON_GROUP_INFO = {
    title: 'Skeleton',
    text: <p>How the connected skeleton is placed on the triangulated keypoints. These settings apply immediately.</p>,
};

const FIT_SKELETON_INFO = {
    title: 'Skeleton fitting',
    text: <>
        <p>Fits the connected skeleton to the triangulated keypoints every frame: segment lengths are scaled to
            the person and the skeleton is placed from the anchor segment.</p>
        <p><em>When off, the 3D view shows the triangulated keypoints without a fitted skeleton.</em></p>
    </>,
};

/** Non-modal settings for realtime 3D processing, opened from the streaming toolbar. */
export default function RTPthreeDReconstructionSettings({open, onClose, anchorRef}: {
    open: boolean;
    onClose: () => void;
    /** The trigger's container: clicks there belong to the trigger's own toggle, not "outside". */
    anchorRef?: React.RefObject<HTMLElement | null>;
}) {
    const modalRef = useRef<HTMLDivElement>(null);
    const {pipelineConfig, aggregatorConfig, applyOrUpdatePipelineConfig} = useRealtimePipelineSync();
    useEffect(() => {
        if (!open) return;
        const keyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
        const outsideClick = (event: MouseEvent) => {
            const inside = anchorRef?.current ?? modalRef.current;
            if (!inside?.contains(event.target as Node)) onClose();
        };
        window.addEventListener('keydown', keyDown);
        document.addEventListener('mousedown', outsideClick);
        return () => {window.removeEventListener('keydown', keyDown); document.removeEventListener('mousedown', outsideClick);};
    }, [open, onClose, anchorRef]);
    if (!open) return null;
    return <div ref={modalRef} role="dialog" aria-label={REALTIME_3D_SETTINGS_TITLE}
        className="realtime-settings-flyout border-1 border-black elevated-sharp bg-dark br-2 p-1">
        <div className="realtime-settings-panel bg-middark br-1">
            <header className="realtime-settings-header">
                <h2 className="realtime-settings-title">{REALTIME_3D_SETTINGS_TITLE}</h2>
                <AnchoredInfo title={OVERVIEW_INFO.title} text={OVERVIEW_INFO.text}/>
                <IconButton icon="close-icon" ariaLabel={`Close ${REALTIME_3D_SETTINGS_TITLE}`} className="icon-size-25"
                    onClick={onClose}/>
            </header>
            <div className="realtime-settings-body">
                <SettingsGroupHeading text="Skeleton" info={SKELETON_GROUP_INFO}/>
                <SkeletonAnchorSetting value={aggregatorConfig.anchor_segment_name} onChange={value => applyOrUpdatePipelineConfig({
                    ...pipelineConfig, aggregator_config: {...aggregatorConfig, anchor_segment_name: value},
                })}/>
                <SettingRow label="Fit skeleton" info={FIT_SKELETON_INFO}
                    control={<SettingToggleSwitch label="Fit skeleton" isToggled={aggregatorConfig.skeleton_fitting_enabled}
                        onToggle={enabled => applyOrUpdatePipelineConfig({
                            ...pipelineConfig, aggregator_config: {...aggregatorConfig, skeleton_fitting_enabled: enabled},
                        })}/>}/>
                <TemporalFilterControls/>
            </div>
        </div>
    </div>;
}
