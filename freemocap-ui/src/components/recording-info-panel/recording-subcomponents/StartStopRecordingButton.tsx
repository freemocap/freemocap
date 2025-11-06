import React from 'react';
import {Button, keyframes, Typography} from '@mui/material';
import {styled} from '@mui/system';

interface StartStopButtonProps {
    isRecording: boolean;
    countdown: number | null;
    onClick: () => void;
}

const pulseAnimation = keyframes`
    0% {
        background-color: #fb1402;
    }
    50% {
        background-color: #d43333;
    }
    100% {
        background-color: #fb1402;
    }
`;

// Use shouldForwardProp to prevent isRecording from being passed to the DOM
const PulsingButton = styled(Button, {
    shouldForwardProp: (prop) => prop !== 'isRecording'
})(({isRecording}: { isRecording: boolean | undefined }) => ({
    backgroundColor: isRecording ? '#8d0a02' : '#005d94',
    borderStyle: 'solid',
    borderWidth: '3px',
    borderColor: '#ff55ff',
    padding: 10,
    '&:hover': {
        borderColor: '#fb1402',
        borderWidth: '3px',
    },
    ...(isRecording && {
        animation: `${pulseAnimation} 1.5s infinite ease-in-out`,
    }),
}));

export const StartStopRecordingButton: React.FC<StartStopButtonProps> = ({
                                                                             isRecording,
                                                                             countdown,
                                                                             onClick
                                                                         }) => {
    return (
        <PulsingButton
            onClick={onClick}
            variant="contained"
            isRecording={isRecording}
            fullWidth
            sx={{ml:4}}

        >
            <Typography variant="h6">
                {isRecording ? '🔴 Stop Recording' : '🔴 Start Recording'}
            </Typography>
        </PulsingButton>
    );
};
