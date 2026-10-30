import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {defaultRealtimePipelineConfig} from '../../src/store/slices/realtime/realtime-types';
import CaptureSettings from '../../src/components/mocap-setup/mocap-3dreconstruction-settings';
import PipelineSettings from '../../src/components/pipeline-progress/realtime/realtimepipeline-3dreconstruction-settings';

// Replace only the application boundary; exercise both real settings components
// and their real ToggleComponent click handlers in the browser.
export function useRealtimePipelineSync() {
    const [pipelineConfig, setPipelineConfig] = useState(defaultRealtimePipelineConfig);
    return {
        pipelineConfig, aggregatorConfig: pipelineConfig.aggregator_config,
        isConnected: true, isLoading: false,
        triggerRealtimeApply() {},
        applyOrUpdatePipelineConfig(next: typeof pipelineConfig) {
            (window as any).appliedConfig = next;
            setPipelineConfig(next);
        },
    };
}
export const DEFAULT_REALTIME_FILTER_CONFIG = {
    min_cutoff: 1, beta: 0.007, d_cutoff: 1, fabrik_tolerance: 0.0001,
    fabrik_max_iterations: 20, height_meters: 1.75, noise_sigma: 0.015,
};
export function useMocap() {
    return {skeletonFilterConfig: DEFAULT_REALTIME_FILTER_CONFIG,
        updateSkeletonFilterConfigLocalOnly() {}, replaceSkeletonFilterConfigLocalOnly() {}, isLoading: false};
}

const Settings = location.search === '?pipeline' ? PipelineSettings : CaptureSettings;
createRoot(document.getElementById('root')!).render(<Settings open onClose={() => {}}/>);
