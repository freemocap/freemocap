import React from 'react';
import {useTranslation} from 'react-i18next';
import {useBlender} from '@/hooks/useBlender';
import {useElectronIPC} from '@/services';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import IconButton from '@/components/ui-components/IconButton';
import type {DetectorType} from '@/store/slices/mocap/mocap-slice';

interface BlenderSectionProps {
    recordingFolderPath: string | null | undefined;
    disabled?: boolean;
    /** When provided, the "Open .blend in Blender" button is disabled unless true. */
    hasBlendFile?: boolean;
    /** The freemocap_blender_addon only understands MediaPipe output so far. */
    detectorType?: DetectorType;
}

export const BlenderSection: React.FC<BlenderSectionProps> = ({
    recordingFolderPath,
    disabled = false,
    hasBlendFile,
    detectorType,
}) => {
    const {t} = useTranslation();
    const blenderSupported = detectorType === undefined || detectorType === 'mediapipe';

    const {api, isElectron} = useElectronIPC();
    const {
        effectiveBlenderExePath,
        isUsingManualBlenderPath,
        exportToBlenderEnabled,
        autoOpenBlendFile,
        isExporting,
        isDetecting,
        isOpening,
        lastBlendFilePath,
        error,
        redetectBlender,
        setBlenderExePath,
        clearBlenderExePath,
        setExportToBlenderEnabled,
        setAutoOpenBlendFile,
        triggerBlenderExport,
        triggerOpenInBlender,
        clearError,
    } = useBlender();

    const handleSelectBlenderExe = async (): Promise<void> => {
        if (!isElectron || !api) return;
        try {
            const result: string | null = await api.fileSystem.selectExecutableFile.mutate();
            if (result) {
                setBlenderExePath(result);
            }
        } catch (err) {
            console.error('Failed to select Blender executable:', err);
        }
    };

    const handleProcessWithBlender = (): void => {
        if (!recordingFolderPath) return;
        void triggerBlenderExport(recordingFolderPath);
    };

    const handleOpenInBlender = (): void => {
        if (!recordingFolderPath) return;
        void triggerOpenInBlender(recordingFolderPath);
    };

    const canExport =
        blenderSupported &&
        !!recordingFolderPath &&
        !!effectiveBlenderExePath &&
        !isExporting &&
        !disabled;

    const canOpen =
        !!recordingFolderPath &&
        !!effectiveBlenderExePath &&
        !isOpening &&
        !disabled &&
        (hasBlendFile === undefined || hasBlendFile);

    return (
        <div className="mt-2">
            <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0'}} />
            <div className="flex flex-row items-center gap-1 mb-2">
                <span className="icon processmocap-icon icon-size-20" />
                <p className="text sm text-gray" style={{textTransform: 'uppercase', letterSpacing: 1}}>Blender</p>
            </div>

            <div className="flex flex-col gap-2">
                {error && (
                    <div className="toast-notification error">
                        <div className="flex flex-row items-center justify-content-space-between">
                            <p className="text sm">{error}</p>
                            <IconButton icon="clear-icon" iconSize="icon-size-12" onClick={clearError} title={t("dismissError")} />
                        </div>
                    </div>
                )}

                <div className="flex flex-col gap-1">
                    <div className="input-with-string">
                        <input
                            className="input-field text md"
                            value={effectiveBlenderExePath ?? ''}
                            onChange={(e) => setBlenderExePath(e.target.value || null)}
                            placeholder={isDetecting ? t("blender.detecting") : t("blender.notFound")}
                        />
                        <div className="flex flex-row pos-abs right-4 top-50">
                            {isUsingManualBlenderPath && (
                                <IconButton
                                    icon="clear-icon"
                                    onClick={clearBlenderExePath}
                                    title={t("blender.clearManualPath")}
                                />
                            )}
                            <IconButton
                                icon="save-icon"
                                onClick={redetectBlender}
                                disabled={isDetecting}
                                title={t("blender.redetect")}
                            />
                            <IconButton
                                icon="download-icon"
                                onClick={handleSelectBlenderExe}
                                disabled={!isElectron}
                                title={t("blender.selectExecutable")}
                            />
                        </div>
                    </div>
                    <p className="text sm text-gray">
                        {isUsingManualBlenderPath
                            ? t("blender.usingManual")
                            : effectiveBlenderExePath
                                ? t("blender.autoDetected")
                                : t("blender.browseHint")}
                    </p>
                </div>

                {!blenderSupported && (
                    <p className="text sm text-gray">
                        {t("blender.mediapipeOnly")}
                    </p>
                )}

                <div className="flex flex-col gap-1">
                    <ToggleComponent
                        text={t("blender.exportAfterProcessing")}
                        isToggled={exportToBlenderEnabled && blenderSupported}
                        onToggle={setExportToBlenderEnabled}
                        disabled={!blenderSupported}
                    />
                    <ToggleComponent
                        text={t("blender.autoOpenBlend")}
                        isToggled={autoOpenBlendFile && blenderSupported}
                        onToggle={setAutoOpenBlendFile}
                        disabled={!blenderSupported || !exportToBlenderEnabled}
                    />
                </div>

                <button
                    className="button sm secondary w-full"
                    onClick={handleProcessWithBlender}
                    disabled={!canExport}
                >
                    {isExporting ? t("blender.exporting") : t("blender.processRecording")}
                </button>

                <button
                    className="button sm secondary w-full"
                    onClick={handleOpenInBlender}
                    disabled={!canOpen}
                >
                    {isOpening ? t("blender.opening") : t("blender.openBlend")}
                </button>

                {lastBlendFilePath && (
                    <p className="text sm text-gray" style={{fontFamily: 'monospace'}}>
                        {t("blender.lastExport")} {lastBlendFilePath}
                    </p>
                )}
            </div>
        </div>
    );
};
