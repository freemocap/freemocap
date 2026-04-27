import React from 'react';
import {alpha, Box, IconButton, ToggleButton, ToggleButtonGroup, Tooltip, useTheme} from '@mui/material';
import {
    ContentCopy as ContentCopyIcon,
    DeleteSweep as DeleteSweepIcon,
    Pause as PauseIcon,
    PlayArrow as PlayArrowIcon,
    Save as SaveIcon,
    SaveAlt as ScrollToBottomIcon,
    Search as SearchIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {useTranslation} from 'react-i18next';
import {LogSnapshot} from '@/services/server/server-helpers/log-store';
import {LOG_COLORS} from './constants';

interface Props {
    snapshot: LogSnapshot;
    isPaused: boolean;
    copyFeedback: boolean;
    showSearch: boolean;
    selectedLevels: string[];
    onLevelToggle: (e: React.MouseEvent<HTMLElement>, newLevels: string[]) => void;
    onPauseToggle: () => void;
    onClear: () => void;
    onCopyToClipboard: () => Promise<void>;
    onSaveToDisk: () => void;
    onScrollToBottom: () => void;
    onToggleSearch: () => void;
}

export const LogToolbar: React.FC<Props> = ({
    snapshot,
    isPaused,
    copyFeedback,
    showSearch,
    selectedLevels,
    onLevelToggle,
    onPauseToggle,
    onClear,
    onCopyToClipboard,
    onSaveToDisk,
    onScrollToBottom,
    onToggleSearch,
}) => {
    const theme = useTheme();
    const {t} = useTranslation();

    return (
        <Box
            sx={{
                p: 0.5,
                borderBottom: '1px solid',
                borderColor: theme.palette.divider,
                display: 'flex',
                gap: 1,
                alignItems: 'center',
                flexWrap: 'wrap',
            }}
        >
            <span style={{color: theme.palette.text.primary, fontSize: '0.9em', fontWeight: 'bold'}}>
                {t('serverLogs')}
            </span>

            {snapshot.hasErrors && (
                <Tooltip title={t('errorsDetected')}>
                    <WarningIcon
                        sx={{
                            color: LOG_COLORS.ERROR,
                            fontSize: '1.2em',
                            animation: 'pulse 2s infinite',
                            '@keyframes pulse': {
                                '0%, 100%': {opacity: 1},
                                '50%': {opacity: 0.5},
                            },
                        }}
                    />
                </Tooltip>
            )}

            <ToggleButtonGroup
                size="small"
                value={selectedLevels}
                onChange={onLevelToggle}
                sx={{
                    '.MuiToggleButtonGroup-grouped': {
                        border: `1px solid ${theme.palette.divider} !important`,
                        mx: '1px',
                        '&:not(:first-of-type)': {borderRadius: '2px'},
                        '&:first-of-type': {borderRadius: '2px'},
                    },
                }}
            >
                {Object.entries(LOG_COLORS).map(([level, color]) => {
                    const count = snapshot.countsByLevel[level] || 0;
                    return (
                        <ToggleButton
                            key={level}
                            value={level.toLowerCase()}
                            sx={{
                                py: 0.25,
                                px: 1,
                                minWidth: 0,
                                fontSize: '0.75em',
                                position: 'relative',
                                color: alpha(color, 0.7),
                                '&.Mui-selected': {
                                    backgroundColor: alpha(color, 0.15),
                                    color: color,
                                    '&:hover': {backgroundColor: alpha(color, 0.2)},
                                },
                                '&:hover': {backgroundColor: alpha(color, 0.1)},
                            }}
                        >
                            {level}
                            {count > 0 && (
                                <span style={{marginLeft: '4px', fontSize: '0.8em', opacity: 0.7}}>
                                    ({count})
                                </span>
                            )}
                        </ToggleButton>
                    );
                })}
            </ToggleButtonGroup>

            <Box sx={{ml: 'auto', display: 'flex', gap: 0.5}}>
                <Tooltip title={copyFeedback ? t('copied') : t('copyLogsToClipboard')}>
                    <IconButton
                        size="small"
                        onClick={onCopyToClipboard}
                        sx={{color: copyFeedback ? theme.palette.success.main : theme.palette.text.secondary}}
                    >
                        <ContentCopyIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>

                <Tooltip title={t('saveLogsToFile')}>
                    <IconButton size="small" onClick={onSaveToDisk} sx={{color: theme.palette.text.secondary}}>
                        <SaveIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>

                <Tooltip title="Scroll to bottom">
                    <IconButton size="small" onClick={onScrollToBottom} sx={{color: theme.palette.text.secondary}}>
                        <ScrollToBottomIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>

                <IconButton
                    size="small"
                    onClick={onToggleSearch}
                    sx={{color: showSearch ? theme.palette.primary.main : theme.palette.text.secondary}}
                >
                    <SearchIcon fontSize="small"/>
                </IconButton>

                <IconButton
                    size="small"
                    onClick={onPauseToggle}
                    sx={{color: isPaused ? theme.palette.warning.main : theme.palette.text.secondary}}
                >
                    {isPaused ? <PlayArrowIcon fontSize="small"/> : <PauseIcon fontSize="small"/>}
                </IconButton>

                <IconButton size="small" onClick={onClear} sx={{color: theme.palette.text.secondary}}>
                    <DeleteSweepIcon fontSize="small"/>
                </IconButton>
            </Box>
        </Box>
    );
};
