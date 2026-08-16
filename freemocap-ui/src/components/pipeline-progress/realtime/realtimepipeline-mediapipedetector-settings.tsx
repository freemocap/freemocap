import React, { useCallback, useEffect, useRef } from 'react';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import IconButton from '@/components/ui-components/IconButton';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import { useRealtimePipelineSync } from '@/hooks/useRealtimePipelineSync';
import { DetectorType, MediapipeModelComplexity, RTMPOSE_MODELS } from '@/store/slices/mocap';
import { CameraNodeConfig } from '@/store/slices/realtime/realtime-types';
import { useTranslation } from 'react-i18next';

interface RTPSkeletonSetupProps {
    open: boolean;
    onClose: () => void;
}

const RTPSkeletonSetup: React.FC<RTPSkeletonSetupProps> = ({ open, onClose }) => {
    const { t } = useTranslation();
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
                    <SubactionHeader text={t("detector.skeletonSetup")} />
                    <IconButton icon="close-icon" onClick={onClose} />
                </div>

                {/* Detector toggle */}
                <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                    <span className="text-sm">{t("detector.detector")}</span>
                    <div className="flex flex-row gap-1">
                        <SegmentedControl
                            size="sm"
                            className="segmented-control-sm bg-darkgray"
                            value={detectorType ?? "rtmpose"}
                            options={[
                                { label: "RTMPose", value: "rtmpose" },
                                { label: "MediaPipe", value: "mediapipe" },
                            ]}
                            onChange={(value) => handleCameraNodeUpdate({ detector_type: value as DetectorType })}
                        />
                    </div>
                </div>

                {/* RTMPose settings */}
                {detectorType === "rtmpose" && (
                    <>
                        <p className="text-sm text-gray p-1">
                            {t("detector.rtmposeRealtimeDescription")}
                        </p>

                        {/* Model */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.model")}</span>
                            <div className="flex flex-row gap-1">
                                <SegmentedControl
                                    size="sm"
                                    className="segmented-control-sm bg-darkgray"
                                    value={cameraNodeConfig.rtmpose_model_name ?? "rtmw-x-l_256x192"}
                                    options={RTMPOSE_MODELS}
                                    onChange={(value) => handleCameraNodeUpdate({ rtmpose_model_name: value as any })}
                                />
                            </div>
                        </div>

                        {/* Confidence threshold */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.confidenceThreshold")}</span>
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
                            {t("detector.mediapipeRealtimeDescription")}
                        </p>

                        {/* Model size */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.modelSize")}</span>
                            <div className="flex flex-row gap-1">
                                <SegmentedControl
                                    size="sm"
                                    className="segmented-control-sm bg-darkgray"
                                    value={cameraNodeConfig.mediapipe_model_complexity ?? "lite"}
                                    options={[
                                        { label: t("detector.lite"), value: "lite" },
                                        { label: t("detector.full"), value: "full" },
                                        { label: t("detector.heavy"), value: "heavy" },
                                    ]}
                                    onChange={(value) => handleCameraNodeUpdate({ mediapipe_model_complexity: value as MediapipeModelComplexity })}
                                />
                            </div>
                        </div>

                        {/* Detection confidence */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.detectionConfidence")}</span>
                            <ValueSelector
                                value={cameraNodeConfig.mediapipe_detection_confidence ?? 0.5}
                                min={0} max={1} step={0.05} unit=""
                                onChange={(v) => handleCameraNodeUpdate({ mediapipe_detection_confidence: v })}
                            />
                        </div>

                        {/* Presence confidence */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.presenceConfidence")}</span>
                            <ValueSelector
                                value={cameraNodeConfig.mediapipe_presence_confidence ?? 0.5}
                                min={0} max={1} step={0.05} unit=""
                                onChange={(v) => handleCameraNodeUpdate({ mediapipe_presence_confidence: v })}
                            />
                        </div>

                        {/* Tracking confidence */}
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.trackingConfidence")}</span>
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
