import React, { useEffect, useRef, useState } from 'react';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import ValueSelector from '@/components/ui-components/ValueSelector';

interface RealtimePipelineMediaPipeDetectorSettingsProps {
    open: boolean;
    onClose: () => void;
}

const RealtimePipelineMediaPipeDetectorSettings: React.FC<
    RealtimePipelineMediaPipeDetectorSettingsProps
> = ({ open, onClose }) => {
    const modalRef = useRef<HTMLDivElement>(null);

    // Toggles
    const [smoothLandmarks, setSmoothLandmarks] = useState(true);
    const [segmentation, setSegmentation] = useState(true);
    const [smoothSegmentation, setSmoothSegmentation] = useState(true);
    const [refineFaceLandmarks, setRefineFaceLandmarks] = useState(true);
    const [staticImageMode, setStaticImageMode] = useState(true);

    // Dropdown state (IMPORTANT FIX)
    const [preset, setPreset] = useState("Lite Fastest");

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
            className="file-directory-settings-container draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
        >
            <div className="flex flex-col right-0 p-2 bg-middark br-1 z-1">

                {/* Header */}
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text="MediaPipe Settings" />
                    <button className="button icon-button" onClick={onClose}>
                        <span className="icon close-icon icon-size-20" />
                    </button>
                </div>

                {/* Preset dropdown (FIXED) */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Preset</span>

                    <NameDropdownSelector
                        options={["Lite (Fastest)", "PostHog (Accurate)"]}
                        initialValue={preset}
                        onChange={setPreset}
                        className="flex flex-row"
                    />
                </div>

                {/* Min Detection Confidence */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Min detection confidence</span>
                    <ValueSelector
                        value={0.5}
                        min={0}
                        max={1}
                        unit=""
                        onChange={() => {}}
                    />
                </div>

                {/* Max Tracking Confidence */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Max tracking confidence</span>
                    <ValueSelector
                        value={0.5}
                        min={0}
                        max={1}
                        unit=""
                        onChange={() => {}}
                    />
                </div>

                {/* Toggles */}
                <ToggleComponent
                    text="Smooth landmarks"
                    isToggled={smoothLandmarks}
                    onToggle={setSmoothLandmarks}
                />

                <ToggleComponent
                    text="Segmentation"
                    isToggled={segmentation}
                    onToggle={setSegmentation}
                />

                <ToggleComponent
                    text="Smooth segmentation"
                    isToggled={smoothSegmentation}
                    onToggle={setSmoothSegmentation}
                />

                <ToggleComponent
                    text="Refine face landmarks"
                    isToggled={refineFaceLandmarks}
                    onToggle={setRefineFaceLandmarks}
                />

                <ToggleComponent
                    text="Static image mode"
                    isToggled={staticImageMode}
                    onToggle={setStaticImageMode}
                />
            </div>
        </div>
    );
};

export default RealtimePipelineMediaPipeDetectorSettings;