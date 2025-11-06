import React from 'react';
import { IconButton, InputAdornment, TextField } from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { useAppDispatch } from '@/store';
import { recordingDirectoryChanged } from '@/store/slices/recording/recording-slice';
import { useElectronIPC } from '@/services';

interface DirectoryInputProps {
    baseRecordingFolder: string;
}

export const BaseRecordingDirectoryInput: React.FC<DirectoryInputProps> = ({ baseRecordingFolder }) => {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();

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
        <TextField
            label="Recording Directory"
            value={baseRecordingFolder}
            onChange={handleInputChange}
            fullWidth
            size="small"
            InputProps={{
                endAdornment: (
                    <InputAdornment position="end">
                        <IconButton
                            onClick={handleSelectDirectory}
                            edge="end"
                            disabled={!isElectron}
                        >
                            <FolderOpenIcon />
                        </IconButton>
                    </InputAdornment>
                ),
            }}
        />
    );
};
