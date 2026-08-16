import React, {useCallback, useEffect, useMemo, useState} from "react";
import {useTranslation} from "react-i18next";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {DirectoryStatusPanel} from "@/components/common/DirectoryStatusPanel";
import {useMocap} from "@/hooks/useMocap";
import {useElectronIPC} from "@/services";
import {MediapipeConfigPanel} from "@/components/control-panels/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/control-panels/mocap-control-panel/SkeletonFilterConfigPanel";
import {useCalibration} from "@/hooks/useCalibration";
import IconButton from "@/components/ui-components/IconButton";

export const MocapTaskTreeItem: React.FC = () => {
    const {t} = useTranslation();
    const [localError, setLocalError] = useState<string | null>(null);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const {api, isElectron} = useElectronIPC();

    const {
        error,
        isLoading,
        isRecording,
        recordingProgress,
        canStartRecording,
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

    // Get the most recent calibration recording path from calibration state
    const {
        directoryInfo: calibrationDirectoryInfo,
    } = useCalibration();

    useEffect(() => {
        if (mocapRecordingPath) {
            validateDirectory(mocapRecordingPath);
        }
    }, [mocapRecordingPath, validateDirectory]);

    const handleClearError = useCallback((): void => {
        clearError();
        setLocalError(null);
    }, [clearError]);

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) {
            console.warn("Electron API not available");
            return;
        }
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

    const handlePathInputChange = async (
        e: React.ChangeEvent<HTMLInputElement>
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && isElectron && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(
                    /^~([/\\])?/,
                    home ? `${home}$1` : ""
                );
                await setManualRecordingPath(expanded);
            } catch (err) {
                console.error("Failed to expand home directory:", err);
                await setManualRecordingPath(newPath);
            }
        } else {
            await setManualRecordingPath(newPath);
        }
    };

    const handleClearManualPath = useCallback((): void => {
        clearManualRecordingPath();
    }, [clearManualRecordingPath]);

    const handleRefresh = useCallback(async (): Promise<void> => {
        if (!mocapRecordingPath) return;
        setIsRefreshing(true);
        try {
            await validateDirectory(mocapRecordingPath);
        } finally {
            setTimeout(() => setIsRefreshing(false), 400);
        }
    }, [mocapRecordingPath, validateDirectory]);

    const handleSelectCalibrationToml = async (): Promise<void> => {
        if (!isElectron || !api) {
            console.warn("Electron API not available");
            return;
        }
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

    const displayError = error || localError || directoryInfo?.errorMessage;

    const pathHelperText = useMemo(() => {
        if (isUsingManualPath) return t("mocap.usingCustomPath");
        return t("mocap.usingDefaultDirectory");
    }, [isUsingManualPath, t]);

    // Effective calibration path (considers all sources)
    const effectiveCalibrationTomlPath = useMemo(() => {
        if (calibrationTomlPath) return calibrationTomlPath;
        if (directoryInfo?.cameraMocapTomlPath) return directoryInfo.cameraMocapTomlPath;
        if (calibrationDirectoryInfo?.cameraCalibrationTomlPath) return calibrationDirectoryInfo.cameraCalibrationTomlPath;
        return null;
    }, [calibrationTomlPath, directoryInfo?.cameraMocapTomlPath, calibrationDirectoryInfo?.cameraCalibrationTomlPath]);

    // Mocap status derivation
    const mocapStatus: "ok" | "none" | "bad" = useMemo(() => {
        if (effectiveCalibrationTomlPath) return "ok";
        if (!mocapRecordingPath || !directoryInfo) return "none";
        return "bad";
    }, [effectiveCalibrationTomlPath, mocapRecordingPath, directoryInfo]);

    const mocapStatusIcon = useMemo(() => {
        if (mocapStatus === "ok") {
            return (
                <span title={t("mocap.calibrationReady")}>
                    <span className="icon upToDate-icon icon-size-20" />
                </span>
            );
        }
        if (mocapStatus === "bad") {
            return (
                <span title={t("mocap.noCalibrationAtPath")}>
                    <span className="icon close-icon icon-size-20" />
                </span>
            );
        }
        return (
            <span title={t("mocap.noDirectorySelected")}>
                <span className="icon warning-icon icon-size-20" />
            </span>
        );
    }, [mocapStatus, t]);

    const refreshButton = (
        <IconButton
            icon={isRefreshing ? "loader-icon" : "rotate-icon"}
            onClick={(e) => {
                e.stopPropagation();
                handleRefresh();
            }}
            disabled={!mocapRecordingPath || isLoading || isRefreshing}
            title={mocapRecordingPath ? t("mocap.recheckFolder") : t("mocap.noPathSet")}
        />
    );

    // Derive status for collapsed summary
    const statusLabel = isRecording
        ? t("mocap.recordingPercent", {progress: recordingProgress.toFixed(0)})
        : isLoading
            ? t("mocap.processing")
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

    // Primary controls: status icon + refresh + record start/stop
    const headerControls = (
        <div className="flex flex-row items-center gap-1">
            {mocapStatusIcon}
            {refreshButton}
            {isRecording ? (
                <IconButton
                    icon="stopstreaming-icon"
                    className="icon-size-25 btn-danger"
                    onClick={(e) => {
                        e.stopPropagation();
                        dispatchStopMocapRecording();
                    }}
                    disabled={isLoading}
                    title={t("mocap.stopRecording")}
                />
            ) : (
                <IconButton
                    icon="record-icon"
                    onClick={(e) => {
                        e.stopPropagation();
                        dispatchStartMocapRecording();
                    }}
                    disabled={!canStartRecording || isLoading}
                    title={canStartRecording ? t("mocap.startRecording") : t("mocap.cannotRecordYet")}
                />
            )}
        </div>
    );

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon processmocap-icon icon-size-20" />}
            title={t("mocap.title")}
            summaryContent={
                <span className="tag text sm">{statusLabel}</span>
            }
            primaryControl={headerControls}
            defaultExpanded={false}
        >
            <div className="p-2">
                <div className="flex flex-col gap-2">
                    {/* Error Display */}
                    {displayError && (
                        <div className="toast-notification error">
                            <div className="flex flex-row items-center justify-content-space-between">
                                <p className="text sm">{displayError}</p>
                                <IconButton icon="clear-icon" iconSize="icon-size-12" onClick={handleClearError} title={t("dismiss")} />
                            </div>
                        </div>
                    )}

                    {/* Recording Controls */}
                    <div className="flex flex-row gap-2">
                        <button
                            className="button sm primary flex-1"
                            onClick={dispatchStartMocapRecording}
                            disabled={!canStartRecording || isLoading}
                        >
                            <span className="icon play-icon icon-size-20" /> {t("mocap.startRecording")}
                        </button>
                        {isRecording && (
                            <button
                                className="button sm btn-danger flex-1"
                                onClick={dispatchStopMocapRecording}
                                disabled={isLoading}
                            >
                                <span className="icon stopstreaming-icon icon-size-20" /> {t("stopRecording")}
                            </button>
                        )}
                    </div>

                    {/* Recording Path Input */}
                    <div className="flex flex-col gap-1">
                        <div className="input-with-string pos-rel">
                            <input
                                className="input-field text md"
                                value={mocapRecordingPath ?? ''}
                                onChange={handlePathInputChange}
                                placeholder={t("mocap.recordingPath")}
                            />
                            <div className="flex flex-row pos-abs right-4 top-50">
                                {isUsingManualPath && (
                                    <IconButton
                                        icon="clear-icon"
                                        onClick={handleClearManualPath}
                                        title={t("mocap.clearManualPath")}
                                    />
                                )}
                                <IconButton
                                    icon="load-icon"
                                    onClick={handleSelectDirectory}
                                    disabled={!isElectron}
                                    title={t("mocap.selectDirectory")}
                                />
                            </div>
                        </div>
                        <p className="text sm text-gray">{pathHelperText}</p>
                    </div>

                    {/* Directory Status Info */}
                    <DirectoryStatusPanel
                        title={t("mocap.folderStatus")}
                        tomlLabel={t("mocap.hasCalibrationToml")}
                        directoryInfo={directoryInfo ? {
                            ...directoryInfo,
                            tomlPath: directoryInfo.cameraMocapTomlPath,
                        } : null}
                        status={mocapStatus}
                        onRefresh={handleRefresh}
                        refreshDisabled={!mocapRecordingPath || isLoading || isRefreshing}
                        isRefreshing={isRefreshing}
                    />

                    {/* Calibration TOML Override */}
                    <div className="p-2 br-1 border-1 border-mid-black">
                        <div className="flex flex-col gap-1">
                            <div className="flex flex-row items-center gap-1">
                                <span className="icon file-icon icon-size-20" />
                                <p className="text sm text-gray" style={{fontWeight: 500}}>{t("mocap.calibrationToml")}</p>
                            </div>
                            <p className="text sm text-gray">
                                {calibrationTomlPath
                                    ? t("mocap.usingSpecifiedCalibration")
                                    : effectiveCalibrationTomlPath
                                        ? t("mocap.usingAutoCalibration")
                                        : t("mocap.noCalibrationFound")}
                            </p>
                            {effectiveCalibrationTomlPath && (
                                <p className="text sm block" style={{
                                    fontFamily: "monospace",
                                    color: 'var(--color-success)',
                                    wordBreak: "break-all",
                                }}>
                                    {effectiveCalibrationTomlPath}
                                </p>
                            )}
                            <div className="flex flex-row gap-1">
                                <button
                                    className={`button sm flex-1 ${calibrationTomlPath ? "secondary" : "primary"}`}
                                    onClick={clearCalibrationTomlPath}
                                    disabled={!calibrationTomlPath}
                                >
                                    {t("mocap.useMostRecent")}
                                </button>
                                <button
                                    className={`button sm flex-1 ${calibrationTomlPath ? "primary" : "secondary"}`}
                                    onClick={handleSelectCalibrationToml}
                                    disabled={!isElectron}
                                >
                                    <span className="icon file-icon icon-size-20" /> {t("mocap.selectToml")}
                                </button>
                            </div>
                        </div>
                    </div>

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

                    {/* MediaPipe Detector Config */}
                    <MediapipeConfigPanel />

                    {/* Skeleton Filter Config */}
                    <SkeletonFilterConfigPanel />

                    {/* Process Recording Button */}
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
                </div>
            </div>
        </CollapsibleSidebarSection>
    );
};
