import React, {useCallback, useEffect, useMemo, useState} from "react";
import {useTranslation} from "react-i18next";
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
import IconButton from "@/components/ui-components/IconButton";

export const MocapPanel: React.FC = () => {
    const {t} = useTranslation();
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
        detectorType,
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
            const result: string | null = await api.fileSystem.selectDirectory.mutate({
                defaultPath: mocapRecordingPath || undefined,
            });
            if (result) {
                await setManualRecordingPath(result);
            }
        } catch (err) {
            console.error("Failed to select directory:", err);
            setLocalError(t("mocap.selectDirectoryFailed"));
        }
    };

    const handleOpenFolder = async (): Promise<void> => {
        if (!isElectron || !api || !effectiveMocapPath) return;
        try {
            await api.fileSystem.openFolder.mutate({path: effectiveMocapPath});
        } catch (err) {
            console.error("Failed to open folder:", err);
            setLocalError(t("mocap.openFolderFailed"));
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
            setLocalError(t("mocap.selectTomlFailed"));
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
        ? t("mocap.recordingPercent", {progress: recordingProgress.toFixed(0)})
        : isLoading
            ? t("running")
            : effectiveCalibrationTomlPath
                ? t("mocap.ready")
                : t("mocap.idle");

    const processBlockedReason = useMemo((): string | null => {
        if (canProcessMocapRecording) return null;
        if (isRecording) return t("mocap.blocked.stopRecording");
        if (isLoading) return t("mocap.blocked.processing");
        if (!mocapRecordingPath) return t("mocap.blocked.selectFolder");
        if (!directoryInfo?.hasVideos) return t("mocap.blocked.noVideos");
        const hasAnyCalibration =
            directoryInfo?.cameraCount === 1 ||
            !!calibrationTomlPath ||
            !!directoryInfo?.cameraMocapTomlPath ||
            !!directoryInfo?.lastSuccessfulCalibrationTomlPath;
        if (!hasAnyCalibration) return t("mocap.blocked.noCalibration");
        return t("mocap.blocked.cannotProcess");
    }, [canProcessMocapRecording, isRecording, isLoading, mocapRecordingPath, directoryInfo, calibrationTomlPath, t]);

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon processmocap-icon icon-size-20" />}
            title={t("mocap.title")}
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
                        title={processBlockedReason ?? undefined}
                    >
                        {t("mocap.processSelected")}
                    </button>
                    {processBlockedReason && (
                        <p className="text sm text-gray">{processBlockedReason}</p>
                    )}

                    {displayError && (
                        <div className="toast-notification error">
                            <div className="flex flex-row items-center justify-content-space-between">
                                <p className="text sm">{displayError}</p>
                                <IconButton icon="clear-icon" iconSize="icon-size-12" onClick={handleClearError} title={t("dismiss")} />
                            </div>
                        </div>
                    )}

                    {/* Recording ID — prominent at top level */}
                    {recordingId && (
                        <div className="p-1 br-1 bg-middark">
                            <div className="flex flex-row gap-1 items-center">
                                <p className="text sm text-gray">{t("mocap.recordingId")}</p>
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
                                placeholder={t("mocap.recordingPath")}
                            />
                            <div className="flex flex-row pos-abs right-4 top-50">
                                {isUsingManualPath && (
                                    <IconButton
                                        icon="clear-icon"
                                        onClick={clearManualRecordingPath}
                                        title={t("mocap.clearManualPath")}
                                    />
                                )}
                                <IconButton
                                    icon="save-icon"
                                    onClick={() => {
                                        triggerRefresh();
                                        refreshRecordingStatus();
                                    }}
                                    disabled={!mocapRecordingPath || isLoading}
                                    title={t("directory.recheck")}
                                />
                                <IconButton
                                    icon="streaming-icon"
                                    onClick={handleOpenFolder}
                                    disabled={!isElectron || !effectiveMocapPath}
                                    title={t("openFolder")}
                                />
                                <IconButton
                                    icon="download-icon"
                                    onClick={handleSelectDirectory}
                                    disabled={!isElectron}
                                    title={t("mocap.selectDirectory")}
                                />
                            </div>
                        </div>
                        <p className="text sm text-gray">
                            {isUsingManualPath ? t("mocap.usingCustomPath") : t("mocap.usingDefaultDirectory")}
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
                                {t("mocap.recordingInProgress", {progress: recordingProgress.toFixed(0)})}
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
                        detectorType={detectorType}
                    />
                </div>
            </div>
        </CollapsibleSidebarSection>
    );
};
