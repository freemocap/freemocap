import React, { useCallback, useEffect, useRef } from 'react';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import IconButton from '@/components/ui-components/IconButton';
import ValueSelector from '@/components/ui-components/ValueSelector';
import { useRealtimePipelineSync } from '@/hooks/useRealtimePipelineSync';
import { DetectorType, MediapipeModelComplexity, RTMPOSE_MODELS } from '@/store/slices/mocap';
import { CameraNodeConfig } from '@/store/slices/realtime/realtime-types';

interface RTPSkeletonSetupProps {
    open: boolean;
    onClose: () => void;
}

const MEDIAPIPE_COMPLEXITIES: { label: string; value: MediapipeModelComplexity }[] = [
    { label: "Lite", value: "lite" },
    { label: "Full", value: "full" },
    { label: "Heavy", value: "heavy" },
];

const RTPSkeletonSetup: React.FC<RTPSkeletonSetupProps> = ({ open, onClose }) => {
    const modalRef = useRef<HTMLDivElement>(null);
    const { pipelineConfig, cameraNodeConfig, applyOrUpdatePipelineConfig } = useRealtimePipelineSync();

    const detectorType: DetectorType = cameraNodeConfig.detector_type ?? "rtmpose";

    const handleCameraNodeUpdate = useCallback(
        (updates: Partial<CameraNodeConfig>) => {
            applyOrUpdatePipelineConfig({
                ...pipelineConfig,
                camera_node_config: { ...cameraNodeConfig, ...updates },
            });
        },
        [applyOrUpdatePipelineConfig, pipelineConfig, cameraNodeConfig]
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
            className="RTP-settings-flyout pos-abs top-5 right-0 draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
        >
            <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1">

                {/* Header */}
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text="Skeleton Setup" />
                    <IconButton icon="close-icon" onClick={onClose} />
                </div>

                {/* Detector toggle */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">Detector</span>
                    <div className="flex flex-row gap-1">
                        {(["rtmpose", "mediapipe"] as DetectorType[]).map((type) => (
                            <button
                                key={type}
                                className={`button sm br-1 ${detectorType === type ? "primary accent" : "quaternary"}`}
                                onClick={() => handleCameraNodeUpdate({ detector_type: type })}
                            >
                                {type === "rtmpose" ? "RTMPose" : "MediaPipe"}
                            </button>
                        ))}
                    </div>
                </div>

                {/* RTMPose settings */}
                {detectorType === "rtmpose" && (
                    <>
                        <p className="text-sm text-gray p-1">
                            133 keypoints (body, hands, face) via YOLOX + RTMPose. Uses GPU batched inference when available.
                        </p>

                        {/* Model */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Model</span>
                            <div className="flex flex-row gap-1">
                                {RTMPOSE_MODELS.map(({ label, value }) => (
                                    <button
                                        key={value}
                                        className={`button sm br-1 ${(cameraNodeConfig.rtmpose_model_name ?? "rtmw-x-l_256x192") === value ? "primary accent" : "quaternary"}`}
                                        onClick={() => handleCameraNodeUpdate({ rtmpose_model_name: value })}
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Confidence threshold */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Confidence threshold</span>
                            <ValueSelector
                                value={cameraNodeConfig.rtmpose_confidence_threshold ?? 0.0025}
                                min={0} max={1} step={0.0005} unit=""
                                onChange={(v) => handleCameraNodeUpdate({ rtmpose_confidence_threshold: v })}
                            />
                        </div>
                    </>
                )}

                {/* MediaPipe settings */}
                {detectorType === "mediapipe" && (
                    <>
                        <p className="text-sm text-gray p-1">
                            Body + hands + face via MediaPipe. CPU-only; runs per-camera without GPU batching.
                        </p>

                        {/* Model size */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Model size</span>
                            <div className="flex flex-row gap-1">
                                {MEDIAPIPE_COMPLEXITIES.map(({ label, value }) => (
                                    <button
                                        key={value}
                                        className={`button sm br-1 ${(cameraNodeConfig.mediapipe_model_complexity ?? "lite") === value ? "primary accent" : "quaternary"}`}
                                        onClick={() => handleCameraNodeUpdate({ mediapipe_model_complexity: value })}
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Detection confidence */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Detection confidence</span>
                            <ValueSelector
                                value={cameraNodeConfig.mediapipe_detection_confidence ?? 0.5}
                                min={0} max={1} step={0.05} unit=""
                                onChange={(v) => handleCameraNodeUpdate({ mediapipe_detection_confidence: v })}
                            />
                        </div>

                        {/* Presence confidence */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Presence confidence</span>
                            <ValueSelector
                                value={cameraNodeConfig.mediapipe_presence_confidence ?? 0.5}
                                min={0} max={1} step={0.05} unit=""
                                onChange={(v) => handleCameraNodeUpdate({ mediapipe_presence_confidence: v })}
                            />
                        </div>

                        {/* Tracking confidence */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Tracking confidence</span>
                            <ValueSelector
                                value={cameraNodeConfig.mediapipe_tracking_confidence ?? 0.5}
                                min={0} max={1} step={0.05} unit=""
                                onChange={(v) => handleCameraNodeUpdate({ mediapipe_tracking_confidence: v })}
                            />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default RTPSkeletonSetup;
