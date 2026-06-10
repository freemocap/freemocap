import React, {useCallback, useEffect, useMemo, useState} from "react";
import {useMocap} from "@/hooks/useMocap";
import {useCalibration} from "@/hooks/useCalibration";
import {useDirectoryWatcher} from "@/hooks/useDirectoryWatcher";
import {useElectronIPC} from "@/services";
import {CalibrationTomlPicker} from "@/components/common/CalibrationTomlPicker";
import {RealtimePipelineConfigTree} from "@/components/control-panels/realtime-panel/RealtimePipelineConfigTree";
import {useServer} from "@/services/server/ServerContextProvider";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {BlenderSection} from "@/components/control-panels/mocap-control-panel/BlenderSection";
import {RecordingStatusPanel} from "@/components/common/RecordingStatusPanel";
import {useRecordingStatus} from "@/hooks/useRecordingStatus";
import {selectEffectiveRecordingPath} from "@/store/slices/active-recording/active-recording-slice";
import {useAppSelector} from "@/store";

export const MocapPanel: React.FC = () => {
    const {setOverlayVisibility} = useServer();
    const [localError, setLocalError] = useState<string | null>(null);
    const {api, isElectron} = useElectronIPC();

    const {
        error,
        isLoading,
        isRecording,
        recordingProgress,
        canProcessMocapRecording,
        mocapRecordingPath,
        directoryInfo,
        isUsingManualPath,
        dispatchStopMocapRecording,
        dispatchStartMocapRecording,
        setManualRecordingPath,
        clearManualRecordingPath,
        dispatchProcessMocapRecording,
        validateDirectory,
        calibrationTomlPath,
        setCalibrationTomlPath,
        clearCalibrationTomlPath,
        clearError,
    } = useMocap();

    const {
        directoryInfo: calibrationDirectoryInfo,
    } = useCalibration();

    // Effective path: actual activeRecording if any, otherwise the planned path
    const effectiveMocapPath = useAppSelector(selectEffectiveRecordingPath);

    // Derive recording ID from path (last folder name)
    const recordingId = useMemo(() => {
        if (!mocapRecordingPath) return null;
        const parts = mocapRecordingPath.replace(/[/\\]+$/, "").split(/[/\\]/);
        return parts[parts.length - 1] || null;
    }, [mocapRecordingPath]);

    // Derive parent directory so the backend can resolve non-default recording roots
    const recordingParentDirectory = useMemo(() => {
        if (!mocapRecordingPath) return null;
        const trimmed = mocapRecordingPath.replace(/[/\\]+$/, "");
        const idx = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
        return idx > 0 ? trimmed.slice(0, idx) : null;
    }, [mocapRecordingPath]);

    // Auto-poll directory status
    const {triggerRefresh} = useDirectoryWatcher(
        mocapRecordingPath,
        validateDirectory,
        3000,
    );

    // Pipeline stage toggles (local state — posthoc pipeline stages)
    const [charucoEnabled, setCharucoEnabled] = useState(true);
    const [skeletonEnabled, setSkeletonEnabled] = useState(true);

    useEffect(() => {
        setOverlayVisibility(charucoEnabled, skeletonEnabled);
    }, [charucoEnabled, skeletonEnabled, setOverlayVisibility]);

    const [triangulateEnabled, setTriangulateEnabled] = useState(true);
    const [filterEnabled, setFilterEnabled] = useState(true);
    const [rigidBodyEnabled, setRigidBodyEnabled] = useState(true);

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) return;
        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) {
                await setManualRecordingPath(result);
            }
        } catch (err) {
            console.error("Failed to select directory:", err);
            setLocalError("Failed to select directory");
        }
    };

    const handleOpenFolder = async (): Promise<void> => {
        if (!isElectron || !api || !effectiveMocapPath) return;
        try {
            await api.fileSystem.openFolder.mutate({path: effectiveMocapPath});
        } catch (err) {
            console.error("Failed to open folder:", err);
            setLocalError("Failed to open folder in file explorer");
        }
    };

    const handlePathInputChange = async (
        e: React.ChangeEvent<HTMLInputElement>,
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && isElectron && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(/^~([/\\])?/, home ? home + '$1' : "");
                await setManualRecordingPath(expanded);
            } catch {
                await setManualRecordingPath(newPath);
            }
        } else {
            await setManualRecordingPath(newPath);
        }
    };

    const handleSelectCalibrationToml = async (): Promise<void> => {
        if (!isElectron || !api) return;
        try {
            const result: string | null = await api.fileSystem.selectTomlFile.mutate();
            if (result) {
                setCalibrationTomlPath(result);
            }
        } catch (err) {
            console.error("Failed to select TOML file:", err);
            setLocalError("Failed to select TOML file");
        }
    };

    const effectiveCalibrationTomlPath = useMemo(() => {
        if (calibrationTomlPath) return calibrationTomlPath;
        if (directoryInfo?.cameraMocapTomlPath) return directoryInfo.cameraMocapTomlPath;
        if (calibrationDirectoryInfo?.cameraCalibrationTomlPath) return calibrationDirectoryInfo.cameraCalibrationTomlPath;
        if (directoryInfo?.lastSuccessfulCalibrationTomlPath) return directoryInfo.lastSuccessfulCalibrationTomlPath;
        return null;
    }, [calibrationTomlPath, directoryInfo?.cameraMocapTomlPath, calibrationDirectoryInfo?.cameraCalibrationTomlPath, directoryInfo?.lastSuccessfulCalibrationTomlPath]);

    const tomlSource = useMemo(() => {
        if (calibrationTomlPath) return "manual" as const;
        if (directoryInfo?.cameraMocapTomlPath) return "auto" as const;
        if (calibrationDirectoryInfo?.cameraCalibrationTomlPath) return "calibration-panel" as const;
        if (directoryInfo?.lastSuccessfulCalibrationTomlPath) return "last-successful" as const;
        return "auto" as const;
    }, [calibrationTomlPath, directoryInfo?.cameraMocapTomlPath, calibrationDirectoryInfo?.cameraCalibrationTomlPath, directoryInfo?.lastSuccessfulCalibrationTomlPath]);

    const displayError = error || localError || directoryInfo?.errorMessage;

    const {
        status: recordingStatus,
        isLoading: recordingStatusLoading,
        error: recordingStatusError,
        refresh: refreshRecordingStatus,
    } = useRecordingStatus(recordingId, {
        recordingParentDirectory,
    });

    const statusLabel = isRecording
        ? "Recording " + recordingProgress.toFixed(0) + "%"
        : isLoading
            ? "Running"
            : effectiveCalibrationTomlPath
                ? "Ready"
                : "Idle";

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon processmocap-icon icon-size-20" />}
            title="Motion Capture"
            summaryContent={
                <span className="tag text sm">{statusLabel}</span>
            }
            defaultExpanded={false}
        >
            <div className="p-2">
                <div className="flex flex-col gap-2">
                    {/* Process button at TOP per requirements */}
                    <button
                        className="button sm secondary w-full"
                        onClick={dispatchProcessMocapRecording}
                        disabled={!canProcessMocapRecording || isLoading}
                    >
                        Process Selected Recording
                    </button>

                    {displayError && (
                        <div className="toast-notification error">
                            <div className="flex flex-row items-center justify-content-space-between">
                                <p className="text sm">{displayError}</p>
                                <button className="button icon-button br-1" onClick={handleClearError} title="Dismiss">
                                    <span className="icon clear-icon icon-size-12" />
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Recording ID — prominent at top level */}
                    {recordingId && (
                        <div className="p-1 br-1 bg-middark">
                            <div className="flex flex-row gap-1 items-center">
                                <p className="text sm text-gray">Recording ID</p>
                            </div>
                            <p className="text md text-white" style={{fontFamily: "monospace", fontWeight: 600}}>
                                {recordingId}
                            </p>
                        </div>
                    )}

                    {/* Recording Path Input */}
                    <div className="flex flex-col gap-1">
                        <div className="input-with-string pos-rel">
                            <input
                                className="input-field text md"
                                value={effectiveMocapPath || ''}
                                onChange={handlePathInputChange}
                                placeholder="Mocap Recording Path"
                            />
                            <div className="flex flex-row pos-abs right-4 top-50">
                                {isUsingManualPath && (
                                    <button
                                        className="button icon-button br-1"
                                        onClick={clearManualRecordingPath}
                                        title="Clear manual path (revert to default)"
                                    >
                                        <span className="icon clear-icon icon-size-20" />
                                    </button>
                                )}
                                <button
                                    className="button icon-button br-1"
                                    onClick={() => {
                                        triggerRefresh();
                                        refreshRecordingStatus();
                                    }}
                                    disabled={!mocapRecordingPath || isLoading}
                                    title="Re-check folder"
                                >
                                    <span className="icon save-icon icon-size-20" />
                                </button>
                                <button
                                    className="button icon-button br-1"
                                    onClick={handleOpenFolder}
                                    disabled={!isElectron || !effectiveMocapPath}
                                    title="Open folder in file explorer"
                                >
                                    <span className="icon streaming-icon icon-size-20" />
                                </button>
                                <button
                                    className="button icon-button br-1"
                                    onClick={handleSelectDirectory}
                                    disabled={!isElectron}
                                    title="Select directory"
                                >
                                    <span className="icon download-icon icon-size-20" />
                                </button>
                            </div>
                        </div>
                        <p className="text sm text-gray">
                            {isUsingManualPath ? "Using custom path" : "Using default recording directory"}
                        </p>
                    </div>

                    {/* Recording folder status (collapsed by default) */}
                    {recordingId && (
                        <RecordingStatusPanel
                            status={recordingStatus}
                            isLoading={recordingStatusLoading}
                            error={recordingStatusError}
                            onRefresh={() => {
                                triggerRefresh();
                                refreshRecordingStatus();
                            }}
                            activeCalibrationTomlPath={effectiveCalibrationTomlPath}
                            recordingFolderPath={mocapRecordingPath}
                        />
                    )}

                    {/* Calibration TOML — redesigned compact picker */}
                    <CalibrationTomlPicker
                        tomlPath={effectiveCalibrationTomlPath}
                        source={tomlSource}
                        onSelect={handleSelectCalibrationToml}
                        onUseAutoDetected={clearCalibrationTomlPath}
                        disabled={!isElectron}
                    />

                    {/* Recording Progress */}
                    {isRecording && (
                        <div className="w-full">
                            <p className="text sm text-gray">
                                Recording in Progress: {recordingProgress.toFixed(0)}%
                            </p>
                            <div className="update-progress-track">
                                <div
                                    className="update-progress-fill"
                                    style={{width: `${recordingProgress}%`, transition: 'width 0.3s'}}
                                />
                            </div>
                        </div>
                    )}

                    {/* Hierarchical pipeline config */}
                    <RealtimePipelineConfigTree
                        context="posthoc"
                        charucoEnabled={charucoEnabled}
                        onCharucoToggle={setCharucoEnabled}
                        skeletonEnabled={skeletonEnabled}
                        onSkeletonToggle={setSkeletonEnabled}
                        triangulateEnabled={triangulateEnabled}
                        onTriangulateToggle={setTriangulateEnabled}
                        filterEnabled={filterEnabled}
                        onFilterToggle={setFilterEnabled}
                        rigidBodyEnabled={rigidBodyEnabled}
                        onRigidBodyToggle={setRigidBodyEnabled}
                    />

                    <BlenderSection
                        recordingFolderPath={mocapRecordingPath}
                        disabled={isLoading}
                        hasBlendFile={recordingStatus?.has_blend_file}
                    />
                </div>
            </div>
        </CollapsibleSidebarSection>
    );
};
