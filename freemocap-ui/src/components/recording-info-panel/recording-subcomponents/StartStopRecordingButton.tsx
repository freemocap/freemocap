import React, {useEffect, useState} from 'react';
import {Box, Button, CircularProgress, keyframes, Typography} from '@mui/material';
import {styled} from '@mui/system';

interface StartStopButtonProps {
    isRecording: boolean;
    isPending: boolean;
    countdown: number | null;
    recordingStartTime: number | null;
    onClick: () => void;
}

const pulseAnimation = keyframes`
    0% {
        background-color: #fb1402;
    }
    50% {
        background-color: #711c1c;
    }
    100% {
        background-color: #fb1402;
    }
`;

// Use shouldForwardProp to prevent custom props from being passed to the DOM
const PulsingButton = styled(Button, {
    shouldForwardProp: (prop) => !['isRecording', 'isPending'].includes(prop as string)
})<{ isRecording: boolean; isPending: boolean }>(({ isRecording, isPending }) => ({
    backgroundColor: isRecording ? '#8d0a02' : '#005d94',
    borderStyle: 'solid',
    borderWidth: '3px',
    borderColor: isPending ? '#ffa500' : '#ff55ff',
    padding: 10,
    position: 'relative',
    transition: 'all 0.3s ease',
    opacity: isPending ? 0.8 : 1,
    '&:hover': {
        borderColor: isPending ? '#ffa500' : '#fb1402',
        borderWidth: '3px',
    },
    '&:disabled': {
        opacity: 0.8,
        cursor: 'not-allowed',
    },
    ...(isRecording && !isPending && {
        animation: `${pulseAnimation} 3s infinite ease-in-out`,
    }),
}));

const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    const parts: string[] = [];
    if (hours > 0) {
        parts.push(hours.toString().padStart(2, '0'));
    }
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(secs.toString().padStart(2, '0'));

    return parts.join(':');
};

export const StartStopRecordingButton: React.FC<StartStopButtonProps> = ({
    isRecording,
    isPending,
    countdown,
    recordingStartTime,
    onClick
}) => {
    const [recordingDuration, setRecordingDuration] = useState<number>(0);

    // Update recording duration every second
    useEffect(() => {
        if (!isRecording || !recordingStartTime || isPending) {
            setRecordingDuration(0);
            return;
        }

        const updateDuration = (): void => {
            const now = Date.now();
            const duration = Math.floor((now - recordingStartTime) / 1000);
            setRecordingDuration(duration);
        };

        // Update immediately
        updateDuration();

        // Then update every second
        const interval = setInterval(updateDuration, 1000);

        return () => clearInterval(interval);
    }, [isRecording, recordingStartTime, isPending]);

    const getButtonContent = (): React.ReactNode => {
        // Show countdown if active
        if (countdown !== null && countdown > 0) {
            return (
                <Box display="flex" alignItems="center" gap={1}>
                    <Typography variant="h6">
                        Starting in {countdown}...
                    </Typography>
                </Box>
            );
        }

        // Show pending state
        if (isPending) {
            return (
                <Box display="flex" alignItems="center" gap={1}>
                    <CircularProgress size={20} color="inherit" />
                    <Typography variant="h6">
                        {isRecording ? 'Stopping...' : 'Starting...'}
                    </Typography>
                </Box>
            );
        }

        // Show recording state with duration
        if (isRecording) {
            return (
                <Box display="flex" flexDirection="column" alignItems="center">
                    <Typography variant="h6">
                        🔴 Stop Recording
                    </Typography>
                    <Typography variant="caption" sx={{ fontSize: '0.9rem', fontFamily: 'monospace' }}>
                        {formatDuration(recordingDuration)}
                    </Typography>
                </Box>
            );
        }

        // Default start state
        return (
            <Typography variant="h6">
                🔴 Start Recording
            </Typography>
        );
    };

    return (
        <PulsingButton
            onClick={onClick}
            variant="contained"
            isRecording={isRecording}
            isPending={isPending}
            disabled={isPending || countdown !== null}
            fullWidth
        >
            {getButtonContent()}
        </PulsingButton>
    );
};
