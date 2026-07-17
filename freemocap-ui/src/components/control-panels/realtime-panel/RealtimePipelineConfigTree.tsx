import React, {useCallback} from "react";
import {RealtimePipelineStageTreeItem} from "./RealtimePipelineStageTreeItem";
import {SkeletonFilterConfigPanel} from "@/components/control-panels/mocap-control-panel/SkeletonFilterConfigPanel";
import {useMocap} from "@/hooks/useMocap";
import {useRealtimePipelineSync} from "@/hooks/useRealtimePipelineSync";
import {DetectorType, MediapipeModelComplexity, RTMPoseModelName, RealtimeFilterConfig} from "@/store/slices/mocap";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {pipelineConfigUpdated, resetSkeletonFitter} from "@/store/slices/realtime";
import ValueSelector from "@/components/ui-components/ValueSelector";
import {selectCalibrationDirectoryInfo} from "@/store/slices/calibration/calibration-slice";

export type PipelineContext = "realtime" | "posthoc";

interface PipelineConfigTreeProps {
    context: PipelineContext;
    // 2D Tracking stage toggles
    charucoEnabled: boolean;
    onCharucoToggle: (newValue: boolean) => void;
    skeletonEnabled: boolean;
    onSkeletonToggle: (newValue: boolean) => void;
    // 3D Reconstruction stage toggles
    triangulateEnabled: boolean;
    onTriangulateToggle: (newValue: boolean) => void;
    filterEnabled: boolean;
    onFilterToggle: (newValue: boolean) => void;
    rigidBodyEnabled: boolean;
    onRigidBodyToggle: (newValue: boolean) => void;
}

const RTMPOSE_MODELS: { label: string; value: RTMPoseModelName }[] = [
    { label: "Default (256×192)", value: "rtmw-x-l_256x192" },
    { label: "High Res (384×288)", value: "rtmw-x-l_384x288" },
    { label: "Fastest (medium)", value: "rtmw-l-m_256x192" },
];

export const RealtimePipelineConfigTree: React.FC<PipelineConfigTreeProps> = ({
    context,
    charucoEnabled,
    onCharucoToggle,
    skeletonEnabled,
    onSkeletonToggle,
    triangulateEnabled,
    onTriangulateToggle,
    filterEnabled,
    onFilterToggle,
    rigidBodyEnabled,
    onRigidBodyToggle,
}) => {
    const dispatch = useAppDispatch();

    // ── Realtime pipeline config (for context="realtime") ──────────────────────
    const pipelineConfig = useAppSelector(state => state.realtime.pipelineConfig);
    const cameraNodeConfig = pipelineConfig.camera_node_config;

    // ── Posthoc (mocap slice) config (for context="posthoc") ──────────────────
    const {
        detectorType: posthocDetectorType,
        rtmPoseModelName,
        rtmPoseConfidenceThreshold,
        mediapipeModelComplexity,
        mediapipeDetectionConfidence,
        mediapipePresenceConfidence,
        mediapipeTrackingConfidence,
        setDetectorType: setPosThocDetectorType,
        setRtmPoseModelName,
        setRtmPoseConfidenceThreshold,
        setMediapipeModelComplexity,
        setMediapipeDetectionConfidence,
        setMediapipePresenceConfidence,
        setMediapipeTrackingConfidence,
        updateSkeletonFilterConfigLocalOnly,
        replaceSkeletonFilterConfigLocalOnly,
    } = useMocap();

    const {triggerRealtimeApply, isConnected} = useRealtimePipelineSync();
    const calibrationDirectoryInfo = useAppSelector(selectCalibrationDirectoryInfo);

    // ── Active detector type unified across contexts ───────────────────────────
    const activeDetectorType: DetectorType =
        context === "realtime"
            ? (cameraNodeConfig.detector_type ?? "rtmpose")
            : (posthocDetectorType ?? "rtmpose");

    // ── Realtime camera node config updater ───────────────────────────────────
    const handleCameraNodeConfigUpdate = useCallback(
        (updates: Partial<typeof cameraNodeConfig>) => {
            dispatch(pipelineConfigUpdated({
                ...pipelineConfig,
                camera_node_config: { ...cameraNodeConfig, ...updates },
            }));
            triggerRealtimeApply();
        },
        [dispatch, pipelineConfig, cameraNodeConfig, triggerRealtimeApply]
    );

    const handleSetDetectorType = useCallback((type: DetectorType) => {
        if (context === "realtime") {
            handleCameraNodeConfigUpdate({ detector_type: type });
        } else {
            setPosThocDetectorType(type);
        }
    }, [context, handleCameraNodeConfigUpdate, setPosThocDetectorType]);

    // ── Skeleton filter config ─────────────────────────────────────────────────
    const handleUpdateSkeletonFilterConfig = useCallback(
        (updates: Partial<RealtimeFilterConfig>) => {
            updateSkeletonFilterConfigLocalOnly(updates);
            if (context === "realtime") triggerRealtimeApply();
        },
        [updateSkeletonFilterConfigLocalOnly, context, triggerRealtimeApply]
    );

    const handleReplaceSkeletonFilterConfig = useCallback(
        (config: RealtimeFilterConfig) => {
            replaceSkeletonFilterConfigLocalOnly(config);
            if (context === "realtime") triggerRealtimeApply();
        },
        [replaceSkeletonFilterConfigLocalOnly, context, triggerRealtimeApply]
    );

    // ── 2D Tracking parent state ──────────────────────────────────────────────
    const tracking2dAllOn = charucoEnabled && skeletonEnabled;
    const tracking2dSomeOn = charucoEnabled || skeletonEnabled;
    const tracking2dIndeterminate = tracking2dSomeOn && !tracking2dAllOn;
    const tracking2dChecked = tracking2dAllOn;

    // ── 3D Reconstruction parent state ────────────────────────────────────────
    const recon3dAllOn = triangulateEnabled && filterEnabled && rigidBodyEnabled;
    const recon3dSomeOn = triangulateEnabled || filterEnabled || rigidBodyEnabled;
    const recon3dIndeterminate = recon3dSomeOn && !recon3dAllOn;
    const recon3dChecked = recon3dAllOn;

    const handleToggle2dTracking = (newValue: boolean) => {
        onCharucoToggle(newValue);
        onSkeletonToggle(newValue);
    };

    const handleToggle3dReconstruction = (newValue: boolean) => {
        onTriangulateToggle(newValue);
        onFilterToggle(newValue);
        onRigidBodyToggle(newValue);
    };

    const handleResetSkeletonFitter = useCallback(() => {
        dispatch(resetSkeletonFitter());
    }, [dispatch]);

    return (
        <div className="flex flex-col">
            {/* ── 2D Tracking ── */}
            <RealtimePipelineStageTreeItem
                itemId="2d-tracking"
                label="2D Tracking"
                checked={tracking2dChecked}
                indeterminate={tracking2dIndeterminate}
                onToggle={handleToggle2dTracking}

                summaryWhenCollapsed={
                    [charucoEnabled && "Charuco", skeletonEnabled && "Skeleton"]
                        .filter(Boolean)
                        .join(" + ") || "Off"
                }
            >
                {/* Charuco */}
                <RealtimePipelineStageTreeItem
                    itemId="2d-charuco"
                    label="Charuco"
                    checked={charucoEnabled}
                    onToggle={onCharucoToggle}

                >
                    <div className="p-1 pl-4">
                        <p className="text sm text-gray">
                            Settings from `Post Processing::Capture Volume Calibration` section
                        </p>
                    </div>
                </RealtimePipelineStageTreeItem>

                {/* Skeleton */}
                <RealtimePipelineStageTreeItem
                    itemId="2d-skeleton"
                    label="Skeleton"
                    checked={skeletonEnabled}
                    onToggle={onSkeletonToggle}
                    summaryWhenCollapsed={activeDetectorType === "rtmpose" ? "RTMPose" : "MediaPipe"}
                >
                    <div className="p-1 flex flex-col gap-1 pl-4" style={{borderLeft: '2px solid var(--color-border-secondary)'}}>

                        {/* Detector toggle */}
                        <div className="flex flex-row gap-1 items-center justify-content-space-between">
                            <span className="text-sm">Detector</span>
                            <div className="flex flex-row gap-1">
                                {(["rtmpose", "mediapipe"] as DetectorType[]).map((type) => (
                                    <button
                                        key={type}
                                        className={`button sm br-1 ${activeDetectorType === type ? "primary accent" : "quaternary"}`}
                                        onClick={() => handleSetDetectorType(type)}
                                    >
                                        {type === "rtmpose" ? "RTMPose" : "MediaPipe"}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* RTMPose settings */}
                        {activeDetectorType === "rtmpose" && context === "posthoc" && (
                            <>
                                <p className="text-sm text-gray">
                                    133 keypoints (body, hands, face) via YOLOX person detection + RTMPose estimation.
                                </p>
                                <div className="flex flex-row gap-1 items-center justify-content-space-between">
                                    <span className="text-sm">Model</span>
                                    <div className="flex flex-row gap-1">
                                        {RTMPOSE_MODELS.map(({ label, value }) => (
                                            <button
                                                key={value}
                                                className={`button sm br-1 ${(rtmPoseModelName ?? "rtmw-x-l_256x192") === value ? "primary accent" : "quaternary"}`}
                                                onClick={() => setRtmPoseModelName(value)}
                                            >
                                                {label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div className="flex flex-row gap-1 items-center justify-content-space-between">
                                    <span className="text-sm">Confidence threshold</span>
                                    <ValueSelector
                                        value={rtmPoseConfidenceThreshold ?? 0.004}
                                        min={0} max={1} step={0.001} unit=""
                                        onChange={setRtmPoseConfidenceThreshold}
                                    />
                                </div>
                            </>
                        )}
                        {activeDetectorType === "rtmpose" && context === "realtime" && (
                            <p className="text-sm text-gray">
                                133 keypoints (body, hands, face) via YOLOX + RTMPose. Uses GPU batched inference when available.
                            </p>
                        )}

                        {/* MediaPipe settings */}
                        {activeDetectorType === "mediapipe" && (
                            <>
                                <p className="text-sm text-gray">
                                    Body + hands + face via MediaPipe. CPU-only; runs per-camera without GPU batching.
                                </p>
                                <div className="flex flex-row gap-1 items-center justify-content-space-between">
                                    <span className="text-sm">Model size</span>
                                    <div className="flex flex-row gap-1">
                                        {(["lite", "full", "heavy"] as MediapipeModelComplexity[]).map((c) => {
                                            const activeComplexity = context === "realtime"
                                                ? (cameraNodeConfig.mediapipe_model_complexity ?? "lite")
                                                : (mediapipeModelComplexity ?? "heavy");
                                            return (
                                                <button
                                                    key={c}
                                                    className={`button sm br-1 ${activeComplexity === c ? "primary accent" : "quaternary"}`}
                                                    onClick={() => context === "realtime"
                                                        ? handleCameraNodeConfigUpdate({ mediapipe_model_complexity: c })
                                                        : setMediapipeModelComplexity(c)
                                                    }
                                                >
                                                    {c.charAt(0).toUpperCase() + c.slice(1)}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                                <div className="flex flex-row gap-1 items-center justify-content-space-between">
                                    <span className="text-sm">Detection confidence</span>
                                    <ValueSelector
                                        value={context === "realtime"
                                            ? (cameraNodeConfig.mediapipe_detection_confidence ?? 0.5)
                                            : (mediapipeDetectionConfidence ?? 0.5)}
                                        min={0} max={1} step={0.05} unit=""
                                        onChange={(v) => context === "realtime"
                                            ? handleCameraNodeConfigUpdate({ mediapipe_detection_confidence: v })
                                            : setMediapipeDetectionConfidence(v)
                                        }
                                    />
                                </div>
                                <div className="flex flex-row gap-1 items-center justify-content-space-between">
                                    <span className="text-sm">Presence confidence</span>
                                    <ValueSelector
                                        value={context === "realtime"
                                            ? (cameraNodeConfig.mediapipe_presence_confidence ?? 0.5)
                                            : (mediapipePresenceConfidence ?? 0.5)}
                                        min={0} max={1} step={0.05} unit=""
                                        onChange={(v) => context === "realtime"
                                            ? handleCameraNodeConfigUpdate({ mediapipe_presence_confidence: v })
                                            : setMediapipePresenceConfidence(v)
                                        }
                                    />
                                </div>
                                <div className="flex flex-row gap-1 items-center justify-content-space-between">
                                    <span className="text-sm">Tracking confidence</span>
                                    <ValueSelector
                                        value={context === "realtime"
                                            ? (cameraNodeConfig.mediapipe_tracking_confidence ?? 0.5)
                                            : (mediapipeTrackingConfidence ?? 0.5)}
                                        min={0} max={1} step={0.05} unit=""
                                        onChange={(v) => context === "realtime"
                                            ? handleCameraNodeConfigUpdate({ mediapipe_tracking_confidence: v })
                                            : setMediapipeTrackingConfidence(v)
                                        }
                                    />
                                </div>
                            </>
                        )}
                    </div>
                </RealtimePipelineStageTreeItem>
            </RealtimePipelineStageTreeItem>

            {/* ── 3D Reconstruction ── */}
            <RealtimePipelineStageTreeItem
                itemId="3d-reconstruction"
                label="3D Reconstruction"
                checked={recon3dChecked}
                indeterminate={recon3dIndeterminate}
                onToggle={handleToggle3dReconstruction}

                summaryWhenCollapsed={
                    [triangulateEnabled && "Triangulate", filterEnabled && "Filter", rigidBodyEnabled && "Skeleton"]
                        .filter(Boolean)
                        .join(" + ") || "Off"
                }
            >
                {/* Triangulate */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-triangulate"
                    label="Triangulate"
                    checked={triangulateEnabled}
                    onToggle={onTriangulateToggle}
                    summaryWhenCollapsed={
                        pipelineConfig.aggregator_config.calibration_toml_path
                            ? "Custom calibration"
                            : calibrationDirectoryInfo?.lastSuccessfulCalibrationTomlPath
                                ? "Auto (last calibration)"
                                : "No calibration"
                    }
                >
                    <div className="p-1 pl-4 flex flex-col gap-1" style={{borderLeft: '2px solid var(--color-border-secondary)'}}>
                        <p className="text-sm text-gray">
                            Calibration TOML used for 3D triangulation.
                            By default the most recent calibration is used automatically.
                        </p>
                        <div className="flex flex-col gap-1">
                            <span className="text-sm" style={{wordBreak: 'break-all', color: 'var(--color-text-secondary)'}}>
                                {pipelineConfig.aggregator_config.calibration_toml_path
                                    ? `Override: ${pipelineConfig.aggregator_config.calibration_toml_path.split('/').pop()}`
                                    : calibrationDirectoryInfo?.lastSuccessfulCalibrationTomlPath
                                        ? `Auto: ${calibrationDirectoryInfo.lastSuccessfulCalibrationTomlPath.split('/').pop()}`
                                        : "No calibration found — run calibration first"
                                }
                            </span>
                            {pipelineConfig.aggregator_config.calibration_toml_path && (
                                <button
                                    className="button sm"
                                    onClick={() => {
                                        dispatch(pipelineConfigUpdated({
                                            ...pipelineConfig,
                                            aggregator_config: {
                                                ...pipelineConfig.aggregator_config,
                                                calibration_toml_path: null,
                                            },
                                        }));
                                        triggerRealtimeApply();
                                    }}
                                >
                                    Clear override (use latest)
                                </button>
                            )}
                        </div>
                    </div>
                </RealtimePipelineStageTreeItem>

                {/* Filter */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-filter"
                    label="Filter"
                    checked={filterEnabled}
                    onToggle={onFilterToggle}

                    summaryWhenCollapsed="One Euro, FABRIK"
                >
                    <div className="p-1 pl-4" style={{borderLeft: '2px solid var(--color-border-secondary)'}}>
                        <SkeletonFilterConfigPanel
                            updateSkeletonFilterConfig={handleUpdateSkeletonFilterConfig}
                            replaceSkeletonFilterConfig={handleReplaceSkeletonFilterConfig}
                        />
                    </div>
                </RealtimePipelineStageTreeItem>

                {/* Skeleton (rigid body) */}
                <RealtimePipelineStageTreeItem
                    itemId="3d-skeleton"
                    label="Skeleton"
                    checked={rigidBodyEnabled}
                    onToggle={onRigidBodyToggle}

                >
                    <div className="p-1 pl-4 flex flex-col gap-1">
                        <p className="text sm text-gray">
                            Skeleton fitter learns bone lengths online. Reset forgets
                            everything and re-seeds from anthropometric priors — the next
                            frame re-fits from scratch.
                        </p>
                        <button
                            className="button sm"
                            onClick={handleResetSkeletonFitter}
                            disabled={!isConnected}
                            title={isConnected ? "Forget learned bone lengths and re-fit from scratch" : "Connect a realtime pipeline first"}
                        >
                            Reset Fitter
                        </button>
                    </div>
                </RealtimePipelineStageTreeItem>
            </RealtimePipelineStageTreeItem>
        </div>
    );
};
