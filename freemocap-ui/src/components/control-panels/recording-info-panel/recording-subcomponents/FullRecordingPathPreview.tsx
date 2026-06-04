// freemocap-ui/src/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview.tsx
import React from 'react';
import {useTranslation} from "react-i18next";
import {useElectronIPC} from "@/services";


interface FullPathPreviewProps {
    directory: string;
    subfolder?: string;
    filename: string;
}

export const FullRecordingPathPreview: React.FC<FullPathPreviewProps> = ({
    directory,
    filename,
    subfolder
}) => {
    const { t } = useTranslation();
    const { api } = useElectronIPC();
    const parts = [
        {text: directory},
        ...(subfolder ? [{text: subfolder}] : []),
        {text: filename}
    ];

    const fullPath: string = parts.map(p => p.text).join('/');

    // Get the directory path only (without the filename)
    const directoryToOpen: string = subfolder
        ? `${directory}/${subfolder}`
        : directory;

    const handleOpenFolder = async () => {
        try {
            await api?.fileSystem.openFolder.mutate({ path: directoryToOpen });
        } catch (error) {
            console.error('Failed to open folder:', error);
        }
    };

    return (
        <div
            className="p-2 br-1 border-1 border-mid-black bg-middark"
        >
            <div className="flex flex-row justify-content-space-between items-center" style={{marginBottom: 8}}>
                {/* Path display */}
                <div className="flex flex-row items-center" style={{flexWrap: 'wrap', gap: 4, flex: 1, minWidth: 0}}>
                    {parts.map((part, index) => (
                        <React.Fragment key={index}>
                            <div className="flex flex-row items-center" style={{borderRadius: 4, paddingLeft: 4, paddingRight: 4}}>
                                <p
                                    className="text sm text-gray"
                                    style={{fontFamily: 'monospace', fontSize: '0.9rem'}}
                                >
                                    {part.text}
                                </p>
                            </div>
                            {index < parts.length - 1 && (
                                <span className="text sm text-gray">›</span>
                            )}
                        </React.Fragment>
                    ))}
                </div>

                <button
                    className="button icon-button br-1"
                    onClick={handleOpenFolder}
                    title={t("openFolder")}
                >
                    <span className="icon streaming-icon icon-size-20" />
                </button>
            </div>
        </div>
    );
};
