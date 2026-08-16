import React, {useCallback} from "react";
import {useTranslation} from "react-i18next";
import {useMocap} from "@/hooks/useMocap";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import {
    detectPreset,
    DetectorPreset,
    LegacyMediapipeModelComplexity,
    MEDIAPIPE_POSTHOC_PRESET,
    MEDIAPIPE_REALTIME_PRESET,
    MediapipeDetectorConfig,
} from "@/store/slices/mocap";

interface MediapipeConfigPanelProps {
    updateDetectorConfig?: (updates: Partial<MediapipeDetectorConfig>) => void;
    replaceDetectorConfig?: (config: MediapipeDetectorConfig) => void;
}

export const MediapipeConfigPanel: React.FC<MediapipeConfigPanelProps> = ({
    updateDetectorConfig: updateDetectorConfigProp,
    replaceDetectorConfig: replaceDetectorConfigProp,
}) => {
    const {t} = useTranslation();
    const modelComplexityLabels: Record<LegacyMediapipeModelComplexity, string> = {
        0: t("detector.liteFastest"),
        1: t("detector.fullBalanced"),
        2: t("detector.heavyAccurate"),
    };
    const {
        detectorConfig,
        updateDetectorConfig: updateDetectorConfigHook,
        replaceDetectorConfig: replaceDetectorConfigHook,
        isLoading,
    } = useMocap();
    const updateDetectorConfig = updateDetectorConfigProp ?? updateDetectorConfigHook;
    const replaceDetectorConfig = replaceDetectorConfigProp ?? replaceDetectorConfigHook;

    const currentPreset = detectPreset(detectorConfig);

    const handlePresetChange = useCallback(
        (preset: DetectorPreset) => {
            if (preset === "realtime") replaceDetectorConfig({...MEDIAPIPE_REALTIME_PRESET});
            else if (preset === "posthoc") replaceDetectorConfig({...MEDIAPIPE_POSTHOC_PRESET});
        },
        [replaceDetectorConfig]
    );

    return (
        <div className="flex flex-col gap-2">
            <p className="text sm text-gray" style={{fontWeight: 600}}>{t("detector.mediapipeDetector")}</p>

            {/* Preset selector */}
            <div className="flex flex-row items-center gap-1">
                <p className="text sm text-gray" style={{minWidth: 48}}>{t("detector.preset")}</p>
                <button
                    className={`button sm ${currentPreset === "realtime" ? "primary" : "secondary"}`}
                    onClick={() => handlePresetChange("realtime")}
                    disabled={isLoading}
                >
                    {t("detector.realtime")}
                </button>
                <button
                    className={`button sm ${currentPreset === "posthoc" ? "primary" : "secondary"}`}
                    onClick={() => handlePresetChange("posthoc")}
                    disabled={isLoading}
                >
                    {t("detector.posthoc")}
                </button>
                {currentPreset === "custom" && (
                    <span className="tag text sm">{t("custom")}</span>
                )}
            </div>

            {/* Model complexity */}
            <div className="flex flex-col gap-1">
                <p className="text sm text-gray">{t("detector.modelComplexity")}</p>
                <select
                    className="input-field text md"
                    value={detectorConfig.model_complexity}
                    onChange={(e) =>
                        updateDetectorConfig({
                            model_complexity: Number(e.target.value) as LegacyMediapipeModelComplexity,
                        })
                    }
                    disabled={isLoading}
                >
                    <option value={0}>{modelComplexityLabels[0]}</option>
                    <option value={1}>{modelComplexityLabels[1]}</option>
                    <option value={2}>{modelComplexityLabels[2]}</option>
                </select>
            </div>

            {/* Confidence sliders */}
            <div>
                <p className="text sm text-gray">
                    {t("detector.minDetectionConfidence")}: {detectorConfig.min_detection_confidence.toFixed(2)}
                </p>
                <input
                    type="range"
                    value={detectorConfig.min_detection_confidence}
                    onChange={(e) =>
                        updateDetectorConfig({min_detection_confidence: parseFloat(e.target.value)})
                    }
                    min={0} max={1} step={0.05} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div>
                <p className="text sm text-gray">
                    {t("detector.minTrackingConfidence")}: {detectorConfig.min_tracking_confidence.toFixed(2)}
                </p>
                <input
                    type="range"
                    value={detectorConfig.min_tracking_confidence}
                    onChange={(e) =>
                        updateDetectorConfig({min_tracking_confidence: parseFloat(e.target.value)})
                    }
                    min={0} max={1} step={0.05} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            {/* Boolean toggles */}
            <div className="flex flex-col gap-1">
                <ToggleComponent
                    text={t("detector.smoothLandmarks")}
                    isToggled={detectorConfig.smooth_landmarks}
                    onToggle={(checked) => updateDetectorConfig({smooth_landmarks: checked})}
                    disabled={isLoading}
                />
                <ToggleComponent
                    text={t("detector.enableSegmentation")}
                    isToggled={detectorConfig.enable_segmentation}
                    onToggle={(checked) => updateDetectorConfig({enable_segmentation: checked})}
                    disabled={isLoading}
                />
                <ToggleComponent
                    text={t("detector.smoothSegmentation")}
                    isToggled={detectorConfig.smooth_segmentation}
                    onToggle={(checked) => updateDetectorConfig({smooth_segmentation: checked})}
                    disabled={isLoading || !detectorConfig.enable_segmentation}
                />
                <ToggleComponent
                    text={t("detector.refineFaceLandmarks")}
                    isToggled={detectorConfig.refine_face_landmarks}
                    onToggle={(checked) => updateDetectorConfig({refine_face_landmarks: checked})}
                    disabled={isLoading}
                />
                <ToggleComponent
                    text={t("detector.staticImageMode")}
                    isToggled={detectorConfig.static_image_mode}
                    onToggle={(checked) => updateDetectorConfig({static_image_mode: checked})}
                    disabled={isLoading}
                />
            </div>
        </div>
    );
};
