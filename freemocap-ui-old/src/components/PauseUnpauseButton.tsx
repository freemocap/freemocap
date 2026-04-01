// freemocap-ui/src/components/PauseUnpauseButton.tsx
import React, {useState} from 'react';
import {Button, CircularProgress, keyframes, Tooltip} from '@mui/material';
import {styled} from '@mui/system';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import {pauseUnpauseThunk} from "@/store/slices/cameras/old-camera-thunks/pause-unpause-thunk";

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
    // backgroundColor: '#1976d2', // MUI primary blue
    borderRadius: '80px',
    padding: '16px',
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


    const handleClick = async () => {
        setIsLoading(true);

        try {
            await pauseUnpauseThunk();
            // Toggle the paused state after successful API call
            setIsPaused(prev => !prev);
        } catch (error) {
            console.error('Failed to pause/unpause cameras:', error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Tooltip title={isPaused ? "Unpause all cameras" : "Pause all cameras"} >
        <PulsingButton
            onClick={handleClick}
            variant="contained"
            pulsing={isPaused ? true : undefined}
            fullWidth
            disabled={disabled || isLoading}
            startIcon={isLoading ? <CircularProgress/> : isPaused ? <PlayArrowIcon/> : <PauseIcon/>}
        >
        </PulsingButton>
        </Tooltip>
    );
};
