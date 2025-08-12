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


const PulsingButton = styled(Button)(({pulsing}: { pulsing: boolean | undefined }) => ({
    backgroundColor: '#9f1810',
    borderStyle: 'solid',
    borderWidth: '1px',
    borderColor: '#000b10',
    padding: 10,
    '&:hover': {
        backgroundColor: '#d32f2f',
    },
    ...(pulsing && {
        animation: `${pulseAnimation} 1.5s infinite ease-in-out`,
    }),
}));

export const StartStopRecordingButton: React.FC<StartStopButtonProps> = ({
                                                                             isRecording,
                                                                             countdown,
                                                                             onClick
                                                                         }) => {
    return (
        <>
            {countdown !== null && (
                <Typography variant="h4" align="center" color="secondary">
                    Starting in {countdown}...
                </Typography>
            )}
            <PulsingButton
                onClick={onClick}
                variant="contained"
                pulsing={isRecording ? true : undefined}
                fullWidth
            >
                <Typography variant={'h6'}>
                {isRecording ? 'Stop Recording' : 'Start Recording'}
                </Typography>
            </PulsingButton>
        </>
    );
};