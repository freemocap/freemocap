import React, { useEffect, useRef, useState } from 'react';
import { Alert, Box, Chip, CircularProgress, IconButton, Snackbar, Tooltip } from '@mui/material';
import type { AlertColor } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import UpdateIcon from '@mui/icons-material/Update';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useTranslation } from 'react-i18next';
import { useAppVersion } from '@/hooks/useAppVersion';
import { useAutoUpdate } from '@/hooks/useAutoUpdate';
import { EXTERNAL_URLS } from '@/constants/external-urls';

interface VersionChipProps {
    /** compact = small inline style for footers; full = larger for settings */
    variant?: 'compact' | 'full';
}

export const VersionChip: React.FC<VersionChipProps> = ({ variant = 'full' }) => {
    const { t } = useTranslation();
    const version = useAppVersion();
    const { status, version: updateVersion, errorMessage, checkForUpdate } = useAutoUpdate();

    const isChecking = status === 'checking';
    const size = variant === 'compact' ? 'small' : 'medium';

    // Snackbar feedback for update check results
    const prevStatusRef = useRef(status);
    const [snackbar, setSnackbar] = useState<{ open: boolean; severity: AlertColor; message: string }>({
        open: false, severity: 'info', message: '',
    });

    // Brief success state on the chip itself
    const [showSuccess, setShowSuccess] = useState(false);

    useEffect(() => {
        const prev = prevStatusRef.current;
        prevStatusRef.current = status;

        // Only react to transitions from 'checking' to a terminal state
        if (prev !== 'checking') return;

        if (status === 'up-to-date') {
            setSnackbar({ open: true, severity: 'success', message: t('upToDate') });
            setShowSuccess(true);
            setTimeout(() => setShowSuccess(false), 3000);
        } else if (status === 'available') {
            setSnackbar({
                open: true,
                severity: 'info',
                message: t('updateAvailableMessage', { version: updateVersion }),
            });
        } else if (status === 'error') {
            setSnackbar({
                open: true,
                severity: 'error',
                message: errorMessage ? `${t('updateError')}: ${errorMessage}` : t('updateError'),
            });
        }
    }, [status, updateVersion, errorMessage, t]);

    if (!version) return null;

    const chipIcon = isChecking
        ? <CircularProgress size={14} color="inherit" />
        : showSuccess
            ? <CheckCircleIcon sx={{ fontSize: variant === 'compact' ? 14 : 18, color: 'success.main' }} />
            : <UpdateIcon sx={{ fontSize: variant === 'compact' ? 14 : 18 }} />;

    return (
        <>
            <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                <Tooltip title={t('checkForUpdates')} arrow>
                    <Chip
                        icon={chipIcon}
                        label={`v${version}`}
                        size={size}
                        variant="outlined"
                        onClick={checkForUpdate}
                        disabled={isChecking}
                        color={showSuccess ? 'success' : 'default'}
                        sx={{
                            cursor: 'pointer',
                            fontFamily: 'monospace',
                            fontSize: variant === 'compact' ? 10 : 12,
                            height: variant === 'compact' ? 22 : undefined,
                            transition: 'all 0.3s ease',
                            '& .MuiChip-icon': {
                                marginLeft: variant === 'compact' ? '4px' : undefined,
                            },
                        }}
                    />
                </Tooltip>
                <Tooltip title="GitHub Releases" arrow>
                    <IconButton
                        size="small"
                        onClick={() => window.open(EXTERNAL_URLS.GITHUB_RELEASES, '_blank')}
                        sx={{
                            padding: variant === 'compact' ? '2px' : '4px',
                            opacity: 0.6,
                            '&:hover': { opacity: 1 },
                        }}
                    >
                        <OpenInNewIcon sx={{ fontSize: variant === 'compact' ? 13 : 16 }} />
                    </IconButton>
                </Tooltip>
            </Box>
            <Snackbar
                open={snackbar.open}
                autoHideDuration={4000}
                onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                <Alert
                    onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
                    severity={snackbar.severity}
                    variant="filled"
                    sx={{ width: '100%' }}
                >
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </>
    );
};
