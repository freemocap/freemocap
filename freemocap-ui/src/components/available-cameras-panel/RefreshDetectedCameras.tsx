// RefreshDetectedCameras.tsx
import React from 'react';
import { CircularProgress, IconButton, Tooltip } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAppDispatch } from '@/store/AppStateStore';
import { detectCameraDevices } from '@/store/thunks/detect-cameras-thunks/detect-cameras-server-thunk';
// import { detectCameraDevices } from '@/store/thunks/detect-cameras-client-thunks';

interface RefreshDetectedCamerasButtonProps {
    isLoading: boolean;
}

export const RefreshDetectedCamerasButton: React.FC<RefreshDetectedCamerasButtonProps> = ({ isLoading }) => {
    const dispatch = useAppDispatch();

    const handleRefresh = () => {
        if (!isLoading) {
            dispatch(detectCameraDevices());
        }
    };

    return (
        <Tooltip title="Redetect available cameras">
            <IconButton
                color="inherit"
                onClick={handleRefresh}
                disabled={isLoading}
            >
                {isLoading ? <CircularProgress size={24} color="inherit" /> : <RefreshIcon />}
            </IconButton>
        </Tooltip>
    );
};
