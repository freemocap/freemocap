import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import { SetupWizard } from '@/components/setup-wizard/SetupWizard';

export const SetupPage: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();

    const handleComplete = useCallback(() => {
        navigate('/');
    }, [navigate]);

    return (
        <Box
            sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'center',
                overflow: 'auto',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.grey[50],
                py: 4,
            }}
        >
            <SetupWizard onComplete={handleComplete} />
        </Box>
    );
};
