import React from 'react';
import {IconButton, InputAdornment, TextField} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import {useAppDispatch} from "@/store/AppStateStore";
import {setRecordingInfo} from "@/store/slices/recordingInfoSlice";

interface DirectoryInputProps {
    value: string;
}
export const BaseRecordingDirectoryInput: React.FC<DirectoryInputProps> = ({value}) => {
    const dispatch = useAppDispatch();

    const handleSelectDirectory = async () => {
        try {
            const result = await window.electronAPI.selectDirectory();
            if (result) {
                dispatch(setRecordingInfo({recordingDirectory: result}));
            }
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };

    const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const newPath = e.target.value;

        // If the path contains a tilde, expand it immediately
        if (newPath.includes('~')) {
            try {
                const expandedPath = await window.electronAPI.expandPath(newPath);
                dispatch(setRecordingInfo({recordingDirectory: expandedPath}));
            } catch (error) {
                console.error('Failed to expand path:', error);
                dispatch(setRecordingInfo({recordingDirectory: newPath}));
            }
        } else {
            dispatch(setRecordingInfo({recordingDirectory: newPath}));
        }
    };

    return (
        <TextField
            label="Recording Directory"
            value={value}
            onChange={handleInputChange}
            fullWidth
            size="small"
            InputProps={{
                endAdornment: (
                    <InputAdornment position="end">
                        <IconButton onClick={handleSelectDirectory} edge="end">
                            <FolderOpenIcon/>
                        </IconButton>
                    </InputAdornment>
                ),
            }}
        />
    );
};
