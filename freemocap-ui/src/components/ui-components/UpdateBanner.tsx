import React from 'react';
import {Alert, Box, Button, LinearProgress, Typography} from '@mui/material';
import {useTranslation} from 'react-i18next';
import {useAutoUpdate} from '@/hooks/useAutoUpdate';

export const UpdateBanner: React.FC = () => {
    const { t } = useTranslation();
    const { status, version, progress, errorMessage, installUpdate } = useAutoUpdate();

    if (status === 'idle' || status === 'checking' || status === 'up-to-date') {
        return null;
    }

    if (status === 'error') {
        return (
            <Alert severity="error" sx={{ borderRadius: 0 }}>
                {t('updateError')}: {errorMessage}
            </Alert>
        );
    }

    if (status === 'downloading') {
        return (
            <Box sx={{ px: 2, py: 1, bgcolor: 'info.main', color: 'info.contrastText' }}>
                <Typography variant="body2" sx={{ mb: 0.5 }}>
                    {t('downloading')} {version && `v${version}`}
                </Typography>
                <LinearProgress variant="determinate" value={progress} sx={{ borderRadius: 1 }} />
            </Box>
        );
    }

    if (status === 'ready') {
        return (
            <Alert
                severity="success"
                sx={{ borderRadius: 0 }}
                action={
                    <Button color="inherit" size="small" onClick={installUpdate}>
                        {t('restartToUpdate')}
                    </Button>
                }
            >
                {t('downloadComplete')} — v{version}
            </Alert>
        );
    }

    // status === 'available'
    return (
        <Alert severity="info" sx={{ borderRadius: 0 }}>
            {t('updateAvailableMessage', { version })}
        </Alert>
    );
};
