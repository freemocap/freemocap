import React from 'react';
import {useTranslation} from 'react-i18next';
import {useAppDispatch} from '@/store';
import {recordingDirectoryChanged} from '@/store/slices/recording/recording-slice';
import {useElectronIPC} from '@/services';

interface DirectoryInputProps {
    value: string;
}

export const BaseRecordingDirectoryInput: React.FC<DirectoryInputProps> = ({ value }) => {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();
    const { t } = useTranslation();

    const handleSelectDirectory = async (): Promise<void> => {
        // Only try to use electron API if we're in electron environment
        if (!isElectron || !api) {
            console.warn('Electron API not available');
            return;
        }

        try {
            const result: string | null = await api.fileSystem.selectDirectory.mutate();
            if (result) {
                // Use the specific action for recording directory changes
                dispatch(recordingDirectoryChanged(result));
            }
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };

    const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
        const newPath: string = e.target.value;

        // Handle tilde expansion for home directory
        if (newPath.includes('~') && isElectron && api) {
            try {
                const home: string = await api.fileSystem.getHomeDirectory.query();
                // Replace ~ at the beginning of the path with home directory
                const expanded: string = newPath.replace(/^~(\/|\\)?/, home ? `${home}$1` : '');
                dispatch(recordingDirectoryChanged(expanded));
            } catch (error) {
                console.error('Failed to expand home directory:', error);
                // Fall back to using the path as-is
                dispatch(recordingDirectoryChanged(newPath));
            }
        } else {
            dispatch(recordingDirectoryChanged(newPath));
        }
    };

    return (
        <div className="input-with-string pos-rel w-full">
            <input
                className="input-field text md w-full"
                value={value}
                onChange={handleInputChange}
                placeholder={t("recordingDirectory")}
            />
            <button
                className="button icon-button br-1"
                onClick={handleSelectDirectory}
                disabled={!isElectron}
                title={t("recordingDirectory")}
                style={{position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)'}}
            >
                <span className="icon download-icon icon-size-20" />
            </button>
        </div>
    );
};
