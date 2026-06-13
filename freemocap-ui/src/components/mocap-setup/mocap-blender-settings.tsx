import React, { useCallback, useEffect, useRef } from 'react';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import IconButton from '@/components/ui-components/IconButton';
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import ValueSelector from '@/components/ui-components/ValueSelector';
import { useMocap } from '@/hooks/useMocap';
import { useRealtimePipelineSync } from '@/hooks/useRealtimePipelineSync';
import {
    detectPreset,
    MEDIAPIPE_POSTHOC_PRESET,
    MEDIAPIPE_REALTIME_PRESET,
    MediapipeDetectorConfig,
} from '@/store/slices/mocap';

interface MOCAPBlenderSettingsProps {
    open: boolean;
    onClose: () => void;
}

const PRESET_OPTIONS = ["Lite (Fastest)", "PostHog (Accurate)", "Custom"];

const presetLabelToTarget: Record<string, "realtime" | "posthoc"> = {
    "Lite (Fastest)": "realtime",
    "PostHog (Accurate)": "posthoc",
};

const presetValueToLabel: Record<string, string> = {
    realtime: "Lite (Fastest)",
    posthoc: "PostHog (Accurate)",
    custom: "Custom",
};

const MOCAPBlenderSettings: React.FC<
    MOCAPBlenderSettingsProps
> = ({ open, onClose }) => {
    const modalRef = useRef<HTMLDivElement>(null);

    const {
        detectorConfig,
        updateDetectorConfigLocalOnly,
        replaceDetectorConfigLocalOnly,
        isLoading,
    } = useMocap();
    const { triggerRealtimeApply } = useRealtimePipelineSync();

    const handleUpdateDetectorConfig = useCallback(
        (updates: Partial<MediapipeDetectorConfig>) => {
            updateDetectorConfigLocalOnly(updates);
            triggerRealtimeApply();
        },
        [updateDetectorConfigLocalOnly, triggerRealtimeApply]
    );

    const handleReplaceDetectorConfig = useCallback(
        (config: MediapipeDetectorConfig) => {
            replaceDetectorConfigLocalOnly(config);
            triggerRealtimeApply();
        },
        [replaceDetectorConfigLocalOnly, triggerRealtimeApply]
    );

    const currentPreset = detectPreset(detectorConfig);

    const handlePresetChange = useCallback(
        (label: string) => {
            const target = presetLabelToTarget[label];
            if (target === "realtime") handleReplaceDetectorConfig({...MEDIAPIPE_REALTIME_PRESET});
            else if (target === "posthoc") handleReplaceDetectorConfig({...MEDIAPIPE_POSTHOC_PRESET});
        },
        [handleReplaceDetectorConfig]
    );

    useEffect(() => {
        if (!open) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };

        const handleClickOutside = (e: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
                onClose();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        document.addEventListener('mousedown', handleClickOutside);

        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            ref={modalRef}
            className="flex flex-col w-full br-2 reveal fadeIn gap-1"
        >
            <div className="gap-1 flex flex-col">

                {/* Header */}
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text="Blender settings" />
                    {/* <IconButton icon="close-icon" onClick={onClose} /> */}
                </div>

                {/* Preset dropdown */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Preset</span>

                    <NameDropdownSelector
                        key={currentPreset}
                        options={PRESET_OPTIONS}
                        initialValue={presetValueToLabel[currentPreset]}
                        onChange={handlePresetChange}
                        className="flex flex-row"
                    />
                </div>

                {/* Min Detection Confidence */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Min detection confidence</span>
                    <ValueSelector
                        value={detectorConfig.min_detection_confidence}
                        min={0}
                        max={1}
                        step={0.05}
                        unit=""
                        onChange={(v) => handleUpdateDetectorConfig({ min_detection_confidence: v })}
                    />
                </div>

                {/* Min Tracking Confidence */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Min tracking confidence</span>
                    <ValueSelector
                        value={detectorConfig.min_tracking_confidence}
                        min={0}
                        max={1}
                        step={0.05}
                        unit=""
                        onChange={(v) => handleUpdateDetectorConfig({ min_tracking_confidence: v })}
                    />
                </div>

                {/* Toggles */}
                <ToggleComponent
                    text="Smooth landmarks"
                    isToggled={detectorConfig.smooth_landmarks}
                    onToggle={(checked) => handleUpdateDetectorConfig({ smooth_landmarks: checked })}
                    disabled={isLoading}
                />

                <ToggleComponent
                    text="Segmentation"
                    isToggled={detectorConfig.enable_segmentation}
                    onToggle={(checked) => handleUpdateDetectorConfig({ enable_segmentation: checked })}
                    disabled={isLoading}
                />

                <ToggleComponent
                    text="Smooth segmentation"
                    isToggled={detectorConfig.smooth_segmentation}
                    onToggle={(checked) => handleUpdateDetectorConfig({ smooth_segmentation: checked })}
                    disabled={isLoading || !detectorConfig.enable_segmentation}
                />

                <ToggleComponent
                    text="Refine face landmarks"
                    isToggled={detectorConfig.refine_face_landmarks}
                    onToggle={(checked) => handleUpdateDetectorConfig({ refine_face_landmarks: checked })}
                    disabled={isLoading}
                />

                <ToggleComponent
                    text="Static image mode"
                    isToggled={detectorConfig.static_image_mode}
                    onToggle={(checked) => handleUpdateDetectorConfig({ static_image_mode: checked })}
                    disabled={isLoading}
                />
            </div>
        </div>
    );
};

export default MOCAPBlenderSettings;
