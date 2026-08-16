import React, { useEffect, useRef } from 'react';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import { useMocap } from '@/hooks/useMocap';
import { DetectorType, MediapipeModelComplexity, RTMPOSE_MODELS, RTMPoseModelName } from '@/store/slices/mocap';
import { useTranslation } from 'react-i18next';

interface MOCAPDetectorSettingsProps {
    open: boolean;
    onClose: () => void;
}

const MOCAPDetectorSettings: React.FC<
    MOCAPDetectorSettingsProps
> = ({ open, onClose }) => {
    const { t } = useTranslation();
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
                    <SubactionHeader text={t("detector.settings")} />
                </div>

                {/* Detector type toggle */}
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
                            onChange={(value) => setDetectorType(value as DetectorType)}
                        />
                    </div>
                </div>

                {/* RTMPose settings */}
                {(detectorType ?? "rtmpose") === "rtmpose" && (
                    <>
                        <div className="flex p-1 flex-col gap-1">
                            <span className="text-sm text-gray">
                                {t("detector.rtmposePosthocDescription")}
                            </span>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.model")}</span>
                            <div className="flex flex-row gap-1">
                                <SegmentedControl
                                    size="sm"
                                    className="segmented-control-sm bg-darkgray"
                                    value={rtmPoseModelName ?? "rtmw-x-l_256x192"}
                                    options={RTMPOSE_MODELS}
                                    onChange={(value) =>
                                        setRtmPoseModelName(value as RTMPoseModelName)
                                    }
                                />
                            </div>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.confidenceThreshold")}</span>
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
                                {t("detector.mediapipeDescription")}
                            </span>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.modelSize")}</span>
                            <div className="flex flex-row gap-1">
                                <SegmentedControl
                                    size="sm"
                                    className="segmented-control-sm bg-darkgray"
                                    value={mediapipeModelComplexity ?? "heavy"}
                                    options={[
                                        { label: t("detector.heavy"), value: "heavy" },
                                        { label: t("detector.full"), value: "full" },
                                        { label: t("detector.lite"), value: "lite" },
                                    ]}
                                    onChange={(value) => setMediapipeModelComplexity(value as MediapipeModelComplexity)}
                                />
                            </div>
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.detectionConfidence")}</span>
                            <ValueSelector value={mediapipeDetectionConfidence ?? 0.5} min={0} max={1} step={0.05} unit="" onChange={setMediapipeDetectionConfidence} />
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.presenceConfidence")}</span>
                            <ValueSelector value={mediapipePresenceConfidence ?? 0.5} min={0} max={1} step={0.05} unit="" onChange={setMediapipePresenceConfidence} />
                        </div>
                        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">{t("detector.trackingConfidence")}</span>
                            <ValueSelector value={mediapipeTrackingConfidence ?? 0.5} min={0} max={1} step={0.05} unit="" onChange={setMediapipeTrackingConfidence} />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default MOCAPDetectorSettings;
