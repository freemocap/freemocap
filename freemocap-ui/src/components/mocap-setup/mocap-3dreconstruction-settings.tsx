import React from 'react';
import CameraMatchingSettings from './camera-matching-settings';
import {PosthocFilterConfigPanel} from '@/components/control-panels/mocap-control-panel/PosthocFilterConfigPanel';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {cameraMatchingUpdated} from '@/store/slices/mocap';

export default function MOCAPthreeDReconstructionSettings({open, onClose}: {open: boolean; onClose: () => void}) {
    const dispatch = useAppDispatch();
    const cameraMatching = useAppSelector(state => state.mocap.config.cameraMatching);
    if (!open) return null;
    return <div className="flex flex-col w-full br-2 gap-1">
        <div className="flex flex-row justify-content-space-between"><strong>Recording reconstruction</strong>
            <button className="button sm" onClick={onClose}>Close settings</button></div>
        <PosthocFilterConfigPanel/>
        <CameraMatchingSettings config={cameraMatching} showFailurePolicy={true}
            onChange={value => dispatch(cameraMatchingUpdated(value))}/>
    </div>;
}
