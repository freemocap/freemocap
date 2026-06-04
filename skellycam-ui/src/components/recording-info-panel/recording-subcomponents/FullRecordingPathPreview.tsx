import React from 'react';
import { useTranslation } from "react-i18next";
import ButtonSm from '@/components/ui-components/ButtonSm';
import { useElectronIPC } from "@/services";

interface FullPathPreviewProps {
    directory: string;
    subfolder?: string;
    filename: string;
}

export const FullRecordingPathPreview: React.FC<FullPathPreviewProps> = ({
    directory, filename, subfolder,
}) => {
    const { t } = useTranslation();
    const { api } = useElectronIPC();

    const parts = [
        { text: directory },
        ...(subfolder ? [{ text: subfolder }] : []),
        { text: filename },
    ];

    const directoryToOpen = subfolder ? `${directory}/${subfolder}` : directory;

    const handleOpenFolder = async () => {
        try {
            await api?.fileSystem.openFolder.mutate({ path: directoryToOpen });
        } catch (error) {
            console.error('Failed to open folder:', error);
        }
    };

    return (
        <div className="recording-path-preview bg-middark br-1 border-1 border-black p-1 flex items-center gap-1 flex-wrap">
            {parts.map((part, i) => (
                <React.Fragment key={i}>
                    <div className="recording-path-part">
                        <span className="icon subfolder-icon icon-size-20" />
                        <p className="text sm text-gray">{part.text}</p>
                    </div>
                    {i < parts.length - 1 && (
                        <span className="text sm text-darkgray">/</span>
                    )}
                </React.Fragment>
            ))}
            <div style={{ marginLeft: 'auto' }}>
                <ButtonSm
                    iconClass="import-icon"
                    text=""
                    textColor="text-gray"
                    onClick={handleOpenFolder}
                    title={t("openFolder")}
                />
            </div>
        </div>
    );
};
