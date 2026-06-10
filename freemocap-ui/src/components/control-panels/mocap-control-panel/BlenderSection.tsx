import React from 'react';
import {useBlender} from '@/hooks/useBlender';
import {useElectronIPC} from '@/services';
import ToggleComponent from '@/components/ui-components/ToggleComponent';

interface BlenderSectionProps {
    recordingFolderPath: string | null | undefined;
    disabled?: boolean;
    /** When provided, the "Open .blend in Blender" button is disabled unless true. */
    hasBlendFile?: boolean;
}

export const BlenderSection: React.FC<BlenderSectionProps> = ({
    recordingFolderPath,
    disabled = false,
    hasBlendFile,
}) => {
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
        <div style={{marginTop: 8}}>
            <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0'}} />
            <div className="flex flex-row items-center gap-1" style={{marginBottom: 8}}>
                <span className="icon processmocap-icon icon-size-20" />
                <p className="text sm text-gray" style={{textTransform: 'uppercase', letterSpacing: 1}}>Blender</p>
            </div>

            <div className="flex flex-col gap-2">
                {error && (
                    <div className="toast-notification error">
                        <div className="flex flex-row items-center justify-content-space-between">
                            <p className="text sm">{error}</p>
                            <button className="button icon-button br-1" onClick={clearError} title="Dismiss error">
                                <span className="icon clear-icon icon-size-12" />
                            </button>
                        </div>
                    </div>
                )}

                <div className="flex flex-col gap-1">
                    <div className="input-with-string">
                        <input
                            className="input-field text md"
                            value={effectiveBlenderExePath ?? ''}
                            onChange={(e) => setBlenderExePath(e.target.value || null)}
                            placeholder={isDetecting ? 'Detecting…' : 'No Blender found — select manually'}
                        />
                        <div className="flex flex-row" style={{position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)'}}>
                            {isUsingManualBlenderPath && (
                                <button
                                    className="button icon-button br-1"
                                    onClick={clearBlenderExePath}
                                    title="Clear manual path (revert to auto-detected)"
                                >
                                    <span className="icon clear-icon icon-size-20" />
                                </button>
                            )}
                            <button
                                className="button icon-button br-1"
                                onClick={redetectBlender}
                                disabled={isDetecting}
                                title="Re-detect Blender"
                            >
                                <span className="icon save-icon icon-size-20" />
                            </button>
                            <button
                                className="button icon-button br-1"
                                onClick={handleSelectBlenderExe}
                                disabled={!isElectron}
                                title="Select Blender executable"
                            >
                                <span className="icon download-icon icon-size-20" />
                            </button>
                        </div>
                    </div>
                    <p className="text sm text-gray">
                        {isUsingManualBlenderPath
                            ? 'Using manually selected Blender'
                            : effectiveBlenderExePath
                                ? 'Auto-detected Blender'
                                : 'Click the folder icon to browse for blender.exe'}
                    </p>
                </div>

                <div className="flex flex-col gap-1">
                    <ToggleComponent
                        text="Export to Blender after mocap processing"
                        isToggled={exportToBlenderEnabled}
                        onToggle={setExportToBlenderEnabled}
                    />
                    <ToggleComponent
                        text="Auto-open .blend file in Blender when done"
                        isToggled={autoOpenBlendFile}
                        onToggle={setAutoOpenBlendFile}
                    />
                </div>

                <button
                    className="button sm secondary w-full"
                    onClick={handleProcessWithBlender}
                    disabled={!canExport}
                >
                    {isExporting ? 'Exporting to Blender…' : 'Process Recording with Blender'}
                </button>

                <button
                    className="button sm secondary w-full"
                    onClick={handleOpenInBlender}
                    disabled={!canOpen}
                >
                    {isOpening ? 'Opening…' : 'Open .blend in Blender'}
                </button>

                {lastBlendFilePath && (
                    <p className="text sm text-gray" style={{fontFamily: 'monospace'}}>
                        Last export: {lastBlendFilePath}
                    </p>
                )}
            </div>
        </div>
    );
};
