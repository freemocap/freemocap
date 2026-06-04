import React, {useCallback, useEffect, useMemo, useState} from "react";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {DirectoryStatusPanel} from "@/components/common/DirectoryStatusPanel";
import {useMocap} from "@/hooks/useMocap";
import {useElectronIPC} from "@/services";
import {MediapipeConfigPanel} from "@/components/control-panels/mocap-control-panel/MediapipeConfigPanel";
import {SkeletonFilterConfigPanel} from "@/components/control-panels/mocap-control-panel/SkeletonFilterConfigPanel";
import {useCalibration} from "@/hooks/useCalibration";

export const MocapTaskTreeItem: React.FC = () => {
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
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) {
                await setManualRecordingPath(result);
            }
        } catch (err) {
            console.error("Failed to select directory:", err);
            setLocalError("Failed to select directory");
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
            setLocalError("Failed to select TOML file");
        }
    };

    const displayError = error || localError || directoryInfo?.errorMessage;

    const pathHelperText = useMemo(() => {
        if (isUsingManualPath) return "Using custom path";
        return "Using default recording directory";
    }, [isUsingManualPath]);

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
                <span title="Calibration file found — ready to process">
                    <span className="icon upToDate-icon icon-size-20" />
                </span>
            );
        }
        if (mocapStatus === "bad") {
            return (
                <span title="No calibration file found at this path">
                    <span className="icon close-icon icon-size-20" />
                </span>
            );
        }
        return (
            <span title="No mocap directory selected">
                <span className="icon warning-icon icon-size-20" />
            </span>
        );
    }, [mocapStatus]);

    const refreshButton = (
        <button
            className="button icon-button br-1"
            onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                handleRefresh();
            }}
            disabled={!mocapRecordingPath || isLoading || isRefreshing}
            title={mocapRecordingPath ? "Re-check mocap folder" : "No path set"}
        >
            {isRefreshing ? (
                <span className="icon loader-icon icon-size-20" />
            ) : (
                <span className="icon rotate-icon icon-size-20" />
            )}
        </button>
    );

    // Derive status for collapsed summary
    const statusLabel = isRecording
        ? `Recording ${recordingProgress.toFixed(0)}%`
        : isLoading
            ? "Processing..."
            : effectiveCalibrationTomlPath
                ? "Ready"
                : "Idle";

    // Primary controls: status icon + refresh + record start/stop
    const headerControls = (
        <div className="flex flex-row items-center gap-1">
            {mocapStatusIcon}
            {refreshButton}
            {isRecording ? (
                <button
                    className="button icon-button br-1 btn-danger"
                    onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        dispatchStopMocapRecording();
                    }}
                    disabled={isLoading}
                    title="Stop mocap recording"
                >
                    <span className="icon stopstreaming-icon icon-size-20" />
                </button>
            ) : (
                <button
                    className="button icon-button br-1"
                    onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        dispatchStartMocapRecording();
                    }}
                    disabled={!canStartRecording || isLoading}
                    title={canStartRecording ? "Start mocap recording" : "Cannot record yet"}
                >
                    <span className="icon record-icon icon-size-20" />
                </button>
            )}
        </div>
    );

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon processmocap-icon icon-size-20" />}
            title="Motion Capture"
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
                                <button className="button icon-button br-1" onClick={handleClearError} title="Dismiss">
                                    <span className="icon clear-icon icon-size-12" />
                                </button>
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
                            <span className="icon play-icon icon-size-20" /> Start Mocap Recording
                        </button>
                        {isRecording && (
                            <button
                                className="button sm btn-danger flex-1"
                                onClick={dispatchStopMocapRecording}
                                disabled={isLoading}
                            >
                                <span className="icon stopstreaming-icon icon-size-20" /> Stop Recording
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
                                placeholder="Mocap Recording Path"
                            />
                            <div className="flex flex-row" style={{position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)'}}>
                                {isUsingManualPath && (
                                    <button
                                        className="button icon-button br-1"
                                        onClick={handleClearManualPath}
                                        title="Clear manual path (revert to default)"
                                    >
                                        <span className="icon clear-icon icon-size-20" />
                                    </button>
                                )}
                                <button
                                    className="button icon-button br-1"
                                    onClick={handleSelectDirectory}
                                    disabled={!isElectron}
                                    title="Select directory"
                                >
                                    <span className="icon load-icon icon-size-20" />
                                </button>
                            </div>
                        </div>
                        <p className="text sm text-gray">{pathHelperText}</p>
                    </div>

                    {/* Directory Status Info */}
                    <DirectoryStatusPanel
                        title="Mocap Folder Status"
                        tomlLabel="Has calibration TOML"
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
                                <p className="text sm text-gray" style={{fontWeight: 500}}>Calibration TOML</p>
                            </div>
                            <p className="text sm text-gray">
                                {calibrationTomlPath
                                    ? "Using specified calibration file"
                                    : effectiveCalibrationTomlPath
                                        ? "Using auto-detected calibration"
                                        : "No calibration file found"}
                            </p>
                            {effectiveCalibrationTomlPath && (
                                <p className="text sm" style={{
                                    fontFamily: "monospace",
                                    display: "block",
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
                                    Use Most Recent
                                </button>
                                <button
                                    className={`button sm flex-1 ${calibrationTomlPath ? "primary" : "secondary"}`}
                                    onClick={handleSelectCalibrationToml}
                                    disabled={!isElectron}
                                >
                                    <span className="icon file-icon icon-size-20" /> Select TOML
                                </button>
                            </div>
                        </div>
                    </div>

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

                    {/* MediaPipe Detector Config */}
                    <MediapipeConfigPanel />

                    {/* Skeleton Filter Config */}
                    <SkeletonFilterConfigPanel />

                    {/* Process Recording Button */}
                    <button
                        className="button sm secondary w-full"
                        onClick={dispatchProcessMocapRecording}
                        disabled={!canProcessMocapRecording || isLoading}
                    >
                        Process Selected Recording
                    </button>
                </div>
            </div>
        </CollapsibleSidebarSection>
    );
};
