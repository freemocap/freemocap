// skellycam-ui/src/components/PauseUnpauseButton.tsx
import React, {useState} from 'react';
import {Button, CircularProgress, keyframes} from '@mui/material';
import {styled} from '@mui/system';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import {urlService} from "@/services/urlService";

interface PauseUnpauseButtonProps {
    disabled?: boolean;
}

const pulseAnimation = keyframes`
    0% {
        background-color: rgba(25, 118, 210, 0.8);
    }
    50% {
        background-color: rgba(25, 118, 210, 1);
    }
    100% {
        background-color: rgba(25, 118, 210, 0.8);
    }
`;

const PulsingButton = styled(Button)<{ pulsing?: boolean }>(({pulsing}) => ({
    backgroundColor: '#1976d2', // MUI primary blue
    borderRadius: '8px',
    padding: '10px 16px',
    '&:hover': {
        backgroundColor: '#1565c0', // Darker blue on hover
    },
    ...(pulsing && {
        animation: `${pulseAnimation} 1.5s infinite ease-in-out`,
    }),
}));

export const PauseUnpauseButton: React.FC<PauseUnpauseButtonProps> = ({
                                                                          disabled = false
                                                                      }) => {
    const [isPaused, setIsPaused] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    // Add a timeout to prevent indefinite loading state
    const handleApiCall = async (url: string, successAction: () => void) => {
        setIsLoading(true);

        // Create an AbortController to handle timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

        try {
            const response = await fetch(url, {
                method: 'GET',
                signal: controller.signal
            });

            if (response.ok) {
                successAction();
            } else {
                console.error(`API call failed: ${response.statusText}`);
            }
        } catch (error) {
            console.error('An error occured:', error);
        } finally {
            clearTimeout(timeoutId);
            setIsLoading(false);
        }
    };

    const handlePause = () => {
        const pauseUrl = urlService.getCameraUrls().pauseCameras;
        handleApiCall(pauseUrl, () => {
            console.log('Paused successfully');
            setIsPaused(true);
        });
    };

    const handleUnpause = () => {
        const unpauseUrl = urlService.getCameraUrls().unpauseCameras;
        handleApiCall(unpauseUrl, () => {
            console.log('Unpaused successfully');
            setIsPaused(false);
        });
    };

    const handleClick = () => {
        if (isPaused) {
            handleUnpause();
        } else {
            handlePause();
        }
    };

    return (
        <PulsingButton
            onClick={handleClick}
            variant="contained"
            pulsing={isPaused ? true : undefined}
            fullWidth
            disabled={disabled || isLoading}
            startIcon={isLoading ? undefined : isPaused ? <PlayArrowIcon/> : <PauseIcon/>}
        >
            {isLoading ? <CircularProgress size={24} color="inherit"/> : (isPaused ? 'Resume' : 'Pause')}
        </PulsingButton>
    );
};
