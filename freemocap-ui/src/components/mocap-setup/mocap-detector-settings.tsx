import React, { useEffect, useRef } from 'react';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import { useMocap } from '@/hooks/useMocap';
import { DetectorType, MediapipeModelComplexity, RTMPOSE_MODELS } from '@/store/slices/mocap';

interface MOCAPDetectorSettingsProps {
    open: boolean;
    onClose: () => void;
}

const MEDIAPIPE_COMPLEXITIES: { label: string; value: MediapipeModelComplexity }[] = [
    { label: "Heavy", value: "heavy" },
    { label: "Full", value: "full" },
    { label: "Lite", value: "lite" },
];

const MOCAPDetectorSettings: React.FC<
    MOCAPDetectorSettingsProps
> = ({ open, onClose }) => {
    const modalRef = useRef<HTMLDivElement>(null);

    const {
        detectorType,
        rtmPoseModelName,
        rtmPoseConfidenceThreshold,
        mediapipeModelComplexity,
        mediapipeDetectionConfidence,
        mediapipePresenceConfidence,
        mediapipeTrackingConfidence,
        setDetectorType,
        setRtmPoseModelName,
        setRtmPoseConfidenceThreshold,
        setMediapipeModelComplexity,
        setMediapipeDetectionConfidence,
        setMediapipePresenceConfidence,
        setMediapipeTrackingConfidence,
    } = useMocap();


    useEffect(() => {
        if (!open) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
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
                    <SubactionHeader text="Detector Settings" />
                </div>

                {/* Detector type toggle */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Detector</span>
                    <div className="flex flex-row gap-1">
                        <SegmentedControl
                            size="sm"
                            className="segmented-control-sm bg-darkgray"
                            value={detectorType ?? "rtmpose"}
                            options={[
                                { label: "RTMPose", value: "rtmpose" },
                                { label: "MediaPipe", value: "mediapipe" },
                            ]}
                            onChange={(value) => setDetectorType(value as DetectorType)}
                        />
                    </div>
                </div>

                {/* RTMPose settings */}
                {(detectorType ?? "rtmpose") === "rtmpose" && (
                    <>
                        <div className="flex p-1 flex-col gap-1">
                            <span className="text-sm text-gray">
                                133 keypoints (body, hands, face) via YOLOX person detection + RTMPose estimation. Recommended for best accuracy.
                            </span>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Model</span>
                            <div className="flex flex-row gap-1">
                                <SegmentedControl
                                    size="sm"
                                    className="segmented-control-sm bg-darkgray"
                                    value={rtmPoseModelName ?? "rtmw-x-l_256x192"}
                                    options={RTMPOSE_MODELS}
                                    onChange={(value) => setRtmPoseModelName(value)}
                                />
                            </div>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Confidence threshold</span>
                            <ValueSelector
                                value={rtmPoseConfidenceThreshold ?? 0.004}
                                min={0} max={1} step={0.001} unit=""
                                onChange={setRtmPoseConfidenceThreshold}
                            />
                        </div>
                    </>
                )}

                {/* MediaPipe settings */}
                {(detectorType ?? "rtmpose") === "mediapipe" && (
                    <>
                        <div className="flex p-1 flex-col gap-1">
                            <span className="text-sm text-gray">
                                Body (33 pts) + hands (21 pts each) + face (60 pts) in one pass. Faster on CPU, fewer total keypoints than RTMPose.
                            </span>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Pose model size</span>
                            <div className="flex flex-row gap-1">
                                <SegmentedControl
                                    size="sm"
                                    className="segmented-control-sm bg-darkgray"
                                    value={mediapipeModelComplexity ?? "heavy"}
                                    options={MEDIAPIPE_COMPLEXITIES}
                                    onChange={(value) => setMediapipeModelComplexity(value as MediapipeModelComplexity)}
                                />
                            </div>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Detection confidence</span>
                            <ValueSelector value={mediapipeDetectionConfidence ?? 0.5} min={0} max={1} step={0.05} unit="" onChange={setMediapipeDetectionConfidence} />
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Presence confidence</span>
                            <ValueSelector value={mediapipePresenceConfidence ?? 0.5} min={0} max={1} step={0.05} unit="" onChange={setMediapipePresenceConfidence} />
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Tracking confidence</span>
                            <ValueSelector value={mediapipeTrackingConfidence ?? 0.5} min={0} max={1} step={0.05} unit="" onChange={setMediapipeTrackingConfidence} />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default MOCAPDetectorSettings;
