import React, {useCallback, useMemo, useState} from "react";
import {DirectoryStatusPanel} from "@/components/common/DirectoryStatusPanel";
import {useCalibration} from "@/hooks/useCalibration";
import {useDirectoryWatcher} from "@/hooks/useDirectoryWatcher";
import {useElectronIPC} from "@/services";
import {CalibrationSolverSection} from "@/components/control-panels/calibration-control-panel/CalibrationSolverSection";
import {CharucoBoardConfigSection} from "@/components/control-panels/calibration-control-panel/CharucoBoardConfigSection";
import {CollapsibleSidebarSection} from "@/components/common/CollapsibleSidebarSection";
import {selectEffectiveRecordingPath} from "@/store/slices/active-recording/active-recording-slice";
import {useAppSelector} from "@/store";

export const CalibrationPanel: React.FC = () => {
    const [localError, setLocalError] = useState<string | null>(null);
    const {api, isElectron} = useElectronIPC();

    const {
        error,
        config,
        isLoading,
        isRecording,
        recordingProgress,
        updateCalibrationConfig,
        canCalibrate,
        calibrationRecordingPath,
        directoryInfo,
        isUsingManualPath,
        dispatchStopCalibrationRecording,
        dispatchStartCalibrationRecording,
        setManualRecordingPath,
        clearManualRecordingPath,
        validateDirectory,
        calibrateSelectedRecording,
        clearError,
    } = useCalibration();

    const effectiveCalibrationPath = useAppSelector(selectEffectiveRecordingPath);

    const {triggerRefresh, isWatching} = useDirectoryWatcher(
        calibrationRecordingPath,
        validateDirectory,
        3000,
    );

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
        if (!isElectron || !api || !effectiveCalibrationPath) return;
        try {
            await api.fileSystem.openFolder.mutate({path: effectiveCalibrationPath});
        } catch (err) {
            console.error("Failed to open folder:", err);
            setLocalError("Failed to open folder in file explorer");
        }
    };

    const handlePathInputChange = async (
        e: React.ChangeEvent<HTMLInputElement>,
    ): Promise<void> => {
        const newPath: string = e.target.value;
        if (newPath.includes("~") && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                const expanded: string = newPath.replace(/^~([\/])?/, home ? home + '$1' : "");
                await setManualRecordingPath(expanded);
            } catch {
                await setManualRecordingPath(newPath);
            }
        } else {
            await setManualRecordingPath(newPath);
        }
    };

    const calibStatus: "ok" | "none" | "bad" = useMemo(() => {
        if (directoryInfo?.cameraCalibrationTomlPath) return "ok";
        if (!calibrationRecordingPath || !directoryInfo) return "none";
        return "bad";
    }, [directoryInfo, calibrationRecordingPath]);

    const displayError = error || localError || directoryInfo?.errorMessage;

    const statusLabel = isRecording
        ? "Recording " + recordingProgress.toFixed(0) + "%"
        : isLoading
            ? "Running"
            : directoryInfo?.cameraCalibrationTomlPath
                ? "Calibrated"
                : "Idle";

    const statusColor = isRecording
        ? 'var(--color-danger)'
        : isLoading
            ? 'var(--color-warning)'
            : directoryInfo?.cameraCalibrationTomlPath
                ? 'var(--color-success)'
                : 'var(--color-bg-secondary)';

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon calibrate-icon icon-size-20" style={{color: 'inherit'}}/>}
            title="Capture Volume Calibration"
            summaryContent={
                <span
                    className="tag text sm"
                    style={{marginLeft: 'auto', height: 20, fontSize: 11, fontWeight: 600, backgroundColor: statusColor, color: '#fff'}}
                >
                    {statusLabel}
                </span>
            }
            defaultExpanded={false}
        >
            <div className="p-2">
                <div className="flex flex-col gap-2">
                    {displayError && (
                        <div className="toast-notification error" style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
                            <p className="text sm">{displayError}</p>
                            <button className="button icon-button" onClick={handleClearError}>
                                <span className="icon clear-icon icon-size-20"/>
                            </button>
                        </div>
                    )}

                    {/* Recording Path Input */}
                    <div className="input-with-string" style={{display: 'flex', alignItems: 'center'}}>
                        <input
                            className="input-field text md"
                            value={effectiveCalibrationPath || ''}
                            onChange={handlePathInputChange}
                            placeholder="Calibration Recording Path"
                            style={{flex: 1, minWidth: 0}}
                        />
                        {isUsingManualPath && (
                            <button
                                className="button icon-button"
                                onClick={clearManualRecordingPath}
                                title="Clear manual path (revert to default)"
                            >
                                <span className="icon clear-icon icon-size-20"/>
                            </button>
                        )}
                        <button
                            className="button icon-button"
                            onClick={triggerRefresh}
                            disabled={!calibrationRecordingPath || isLoading}
                            title="Re-check calibration folder"
                        >
                            <span className="icon rotate-icon icon-size-20"/>
                        </button>
                        <button
                            className="button icon-button"
                            onClick={handleOpenFolder}
                            disabled={!isElectron || !effectiveCalibrationPath}
                            title="Open folder in file explorer"
                        >
                            <span className="icon icon-size-20" style={{backgroundImage: 'var(--launch-icon, none)'}}/>
                        </button>
                        <button
                            className="button icon-button"
                            onClick={handleSelectDirectory}
                            disabled={!isElectron}
                            title="Select directory"
                        >
                            <span className="icon icon-size-20" style={{backgroundImage: 'var(--folder-open-icon, none)'}}/>
                        </button>
                    </div>
                    {isUsingManualPath
                        ? <p className="text sm text-gray">Using custom path</p>
                        : <p className="text sm text-gray">Using default recording directory</p>
                    }

                    <button
                        className="button sm primary w-full"
                        onClick={calibrateSelectedRecording}
                        disabled={!canCalibrate || isLoading}
                    >
                        Calibrate Selected Recording
                    </button>

                    <DirectoryStatusPanel
                        title="Calibration Folder Status"
                        tomlLabel="Has calibration TOML"
                        directoryInfo={directoryInfo ? {
                            ...directoryInfo,
                            tomlPath: directoryInfo.cameraCalibrationTomlPath,
                        } : null}
                        status={calibStatus}
                        onRefresh={triggerRefresh}
                        refreshDisabled={!calibrationRecordingPath || isLoading}
                        isRefreshing={false}
                    />

                    <label className="flex flex-row items-center gap-1">
                        <input
                            type="checkbox"
                            checked={config.useGroundplane}
                            onChange={(e) => updateCalibrationConfig({useGroundplane: e.target.checked})}
                            disabled={isLoading}
                            style={{accentColor: 'var(--color-info)'}}
                        />
                        <span className="text sm text-gray">Align to ground plane to initial charuco position</span>
                    </label>

                    <CharucoBoardConfigSection/>

                    <CalibrationSolverSection/>

                    {isRecording && (
                        <div style={{width: '100%'}}>
                            <p className="text sm text-gray" style={{marginBottom: 4}}>
                                Recording in Progress: {recordingProgress.toFixed(0)}%
                            </p>
                            <div style={{width: '100%', height: 8, backgroundColor: 'var(--color-bg-secondary)', borderRadius: 4, overflow: 'hidden'}}>
                                <div
                                    style={{
                                        width: recordingProgress + '%',
                                        height: '100%',
                                        backgroundColor: 'var(--color-info)',
                                        transition: 'width 0.3s',
                                    }}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </CollapsibleSidebarSection>
    );
};
