import React from 'react';
import { useTranslation } from 'react-i18next';
import TextSelector from '@/components/ui-components/TextSelector';
import ButtonSm from '@/components/ui-components/ButtonSm';
import { useAppDispatch } from '@/store';
import { recordingDirectoryChanged } from '@/store/slices/recording/recording-slice';
import { useElectronIPC } from '@/services';

interface DirectoryInputProps {
    value: string;
}

export const BaseRecordingDirectoryInput: React.FC<DirectoryInputProps> = ({ value }) => {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();
    const { t } = useTranslation();

    const handleSelectDirectory = async (): Promise<void> => {
        if (!isElectron || !api) return;
        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) dispatch(recordingDirectoryChanged(result));
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };

    const handleTextChange = async (newPath: string): Promise<void> => {
        if (newPath.includes('~') && isElectron && api) {
            try {
                const home = await api.fileSystem.getHomeDirectory.query();
                const expanded = newPath.replace(/^~(\/|\\)?/, home ? `${home}$1` : '');
                dispatch(recordingDirectoryChanged(expanded));
            } catch {
                dispatch(recordingDirectoryChanged(newPath));
            }
        } else {
            dispatch(recordingDirectoryChanged(newPath));
        }
    };

    return (
        <div className="flex gap-1 items-center">
            <div className="text-selector-constrained">
                <TextSelector
                    value={value}
                    onChange={handleTextChange}
                    placeholder={t("recordingDirectory")}
                    popupClassName="directory-input-popup"
                />
            </div>
            <ButtonSm
                iconClass="import-icon"
                text=""
                textColor="text-gray"
                onClick={handleSelectDirectory}
                buttonType={!isElectron ? "disabled" : ""}
                title={t("browseForDirectory")}
            />
        </div>
    );
};
