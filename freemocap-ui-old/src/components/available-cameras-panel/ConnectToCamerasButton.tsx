// ConnectToCamerasButton.tsx
import React from 'react';
import {Button, Typography} from '@mui/material';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {selectSelectedDevices} from "@/store/slices/cameras-slices/camerasSlice";
import {connectToCameras} from "@/store/thunks/connect-to-cameras-thunk";

interface ConnectToCamerasButtonProps {
    onClick?: () => void;
}

export const ConnectToCamerasButton: React.FC<ConnectToCamerasButtonProps> = ({ onClick }) => {
    const dispatch = useAppDispatch();
    const isLoading = useAppSelector(state => state.cameras.isLoading);
    const selectedCameras = useAppSelector(selectSelectedDevices);

    const handleConnectClick = async () => {
        console.log("ConnectToCamerasButton handleConnectClick", selectedCameras, isLoading);
        if (isLoading) {
            console.log('Camera connection is already in progress');
            return;
        }

        try {
            if (selectedCameras && selectedCameras.length > 0) {
                // If we have an onClick prop, use that (for testing/custom handling)
                if (onClick) {
                    onClick();
                } else {
                    // Otherwise dispatch the thunk which will get the configs from state
                    await dispatch(connectToCameras()).unwrap();
                    console.log('Connected to selected cameras');
                }
            } else {
                console.log('No cameras selected to connect to');
            }
        } catch (error) {
            console.error('Error connecting to cameras:', error);
        }
    };

    const hasSelectedCameras = selectedCameras.length > 0;

    return (
        <Button
            variant="contained"
            onClick={handleConnectClick}
            disabled={!hasSelectedCameras || isLoading}
            sx={{
                ml: 1,
                fontSize: 'small',
                color: extendedPaperbaseTheme.palette.primary.contrastText,
                backgroundColor: "#900078",
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: '#000b10',
                '&:disabled': {
                    backgroundColor: "#9d729c",
                    color: "#333",
                }
            }}
        >
            <Typography variant={'h6'}>
            {isLoading ? 'Connecting...' : 'Connect'}
            </Typography>
        </Button>
    );
};
