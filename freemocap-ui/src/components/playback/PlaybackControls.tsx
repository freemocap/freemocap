import React, { useMemo, useState } from 'react';
import {
    Box,
    Checkbox,
    Collapse,
    FormControlLabel,
    IconButton,
    MenuItem,
    Popover,
    Select,
    Slider,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    Typography,
    useTheme,
} from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import FirstPageIcon from '@mui/icons-material/FirstPage';
import LastPageIcon from '@mui/icons-material/LastPage';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import RepeatIcon from '@mui/icons-material/Repeat';
import SettingsIcon from '@mui/icons-material/Settings';
import type { PlaybackSettings } from './SyncedVideoPlayer';
import { useTranslation } from 'react-i18next';

interface PlaybackControlsProps {
    isPlaying: boolean;
    currentTime: number;
    duration: number;
    playbackRate: number;
    currentFrame: number;
    totalFrames: number;
    fps: number;
    recordingFps?: number;
    settings: PlaybackSettings;
    onSettingsChange: (settings: PlaybackSettings) => void;
    onPlayPause: () => void;
    onSeekDrag: (frame: number) => void;
    onSeekCommit: (frame: number) => void;
    onFrameStep: (delta: number) => void;
    onPlaybackRateChange: (rate: number) => void;
    onSeekToStart: () => void;
    onSeekToEnd: () => void;
    isLooping: boolean;
    onToggleLoop: () => void;
}

const PLAYBACK_RATES = [0.1, 0.25, 0.5, 1, 1.5, 2, 4, 8];

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    currentFrame,
    totalFrames,
    fps,
    recordingFps,
    settings,
    onSettingsChange,
    onPlayPause,
    onSeekDrag,
    onSeekCommit,
    onFrameStep,
    onPlaybackRateChange,
    onSeekToStart,
    onSeekToEnd,
    isLooping,
    onToggleLoop,
}) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const monoFont = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';
    const isDark = theme.palette.mode === 'dark';

    // MUI Slider reads direction from the theme, not CSS.
    // Force LTR so the playback slider never reverses in RTL locales.
    const ltrTheme = useMemo(() => createTheme({ ...theme, direction: 'ltr' }), [theme]);

    // Visible accent colors that work on dark backgrounds
    const accentGreen = '#00ff88';
    const accentBlue = '#29b6f6'; // info.main from theme
    const sliderColor = isDark ? accentBlue : theme.palette.primary.main;
    const playBtnColor = isDark ? '#4caf50' : theme.palette.primary.main;

    // Settings popover
    const [settingsAnchor, setSettingsAnchor] = useState<HTMLElement | null>(null);
    const settingsOpen = Boolean(settingsAnchor);

    // Sync info collapse
    const [syncInfoOpen, setSyncInfoOpen] = useState(true);

    const updateSetting = <K extends keyof PlaybackSettings>(key: K, value: PlaybackSettings[K]) => {
        onSettingsChange({ ...settings, [key]: value });
    };

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5,
                px: 2,
                py: 1,
                backgroundColor: theme.palette.background.paper,
                borderTop: `1px solid ${theme.palette.divider}`,
            }}
        >
            {/* Frame-based slider */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Tooltip title={t("estimatedTime")} placement="top">
                    <Typography variant="caption" sx={{
                        fontFamily: monoFont, minWidth: 70, textAlign: 'right',
                        color: accentGreen, fontWeight: 600, fontSize: '0.8rem',
                    }}>
                        ~{formatTime(currentTime)}
                    </Typography>
                </Tooltip>
                <ThemeProvider theme={ltrTheme}>
                <Slider
                    value={currentFrame}
                    min={0}
                    max={Math.max(totalFrames - 1, 1)}
                    step={1}
                    onChange={(_, value) => onSeekDrag(value as number)}
                    onChangeCommitted={(_, value) => onSeekCommit(value as number)}
                    sx={{
                        flex: 1,
                        color: sliderColor,
                        '& .MuiSlider-thumb': {
                            width: 14, height: 14,
                            transition: 'none',
                            backgroundColor: sliderColor,
                            '&:hover, &.Mui-focusVisible': {
                                boxShadow: `0 0 0 8px ${isDark ? 'rgba(41, 182, 246, 0.16)' : 'rgba(25, 118, 210, 0.16)'}`,
                            },
                        },
                        '& .MuiSlider-track': { transition: 'none', backgroundColor: sliderColor },
                        '& .MuiSlider-rail': { backgroundColor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)' },
                    }}
                    size="small"
                />
                </ThemeProvider>
                <Tooltip title={t("estimatedDuration")} placement="top">
                    <Typography variant="caption" sx={{
                        fontFamily: monoFont, minWidth: 70,
                        color: theme.palette.text.secondary,
                    }}>
                        ~{formatTime(duration)}
                    </Typography>
                </Tooltip>
            </Box>

            {/* Transport controls */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                {/* Left: frame info + recording stats */}
                <Box sx={{ minWidth: 240, textAlign: 'right', mr: 2, display: 'flex', alignItems: 'center', gap: 1.5, justifyContent: 'flex-end' }}>
                    {/* Frame counter badge */}
                    <Typography
                        component="span"
                        sx={{
                            fontFamily: monoFont,
                            fontSize: '0.85rem',
                            fontWeight: 700,
                            color: accentGreen,
                            backgroundColor: 'rgba(0,255,136,0.08)',
                            px: 1, py: 0.25, borderRadius: 1,
                            border: '1px solid rgba(0,255,136,0.2)',
                        }}
                    >
                        Frame {currentFrame} / {totalFrames}
                    </Typography>

                    {/* Recording FPS badge — clearly labeled */}
                    {recordingFps != null && recordingFps > 0 && (
                        <Tooltip title={t("recordingCaptureFps")}>
                            <Typography
                                component="span"
                                sx={{
                                    fontFamily: monoFont,
                                    fontSize: '0.7rem',
                                    color: isDark ? '#ffcc80' : theme.palette.warning.dark,
                                    backgroundColor: isDark ? 'rgba(255,204,128,0.08)' : 'rgba(255,152,0,0.08)',
                                    px: 0.75, py: 0.2, borderRadius: 1,
                                    border: `1px solid ${isDark ? 'rgba(255,204,128,0.2)' : 'rgba(255,152,0,0.2)'}`,
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                rec: {recordingFps} fps
                            </Typography>
                        </Tooltip>
                    )}
                </Box>

                {/* Center: transport buttons — bright colors for visibility */}
                <Tooltip title={t("jumpToStart")}>
                    <IconButton size="small" onClick={onSeekToStart}
                        sx={{ color: isDark ? '#b3b9c6' : undefined }}>
                        <FirstPageIcon />
                    </IconButton>
                </Tooltip>

                <Tooltip title={t("previousFrame")}>
                    <IconButton size="small" onClick={() => onFrameStep(-1)}
                        sx={{ color: isDark ? '#b3b9c6' : undefined }}>
                        <SkipPreviousIcon />
                    </IconButton>
                </Tooltip>

                <Tooltip title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}>
                    <IconButton
                        onClick={onPlayPause}
                        sx={{
                            mx: 1,
                            color: playBtnColor,
                            border: `2px solid ${playBtnColor}`,
                            '&:hover': {
                                backgroundColor: `${playBtnColor}22`,
                                borderColor: playBtnColor,
                            },
                        }}
                    >
                        {isPlaying ? <PauseIcon fontSize="large" /> : <PlayArrowIcon fontSize="large" />}
                    </IconButton>
                </Tooltip>

                <Tooltip title={t("nextFrame")}>
                    <IconButton size="small" onClick={() => onFrameStep(1)}
                        sx={{ color: isDark ? '#b3b9c6' : undefined }}>
                        <SkipNextIcon />
                    </IconButton>
                </Tooltip>

                <Tooltip title={t("jumpToEnd")}>
                    <IconButton size="small" onClick={onSeekToEnd}
                        sx={{ color: isDark ? '#b3b9c6' : undefined }}>
                        <LastPageIcon />
                    </IconButton>
                </Tooltip>

                <Tooltip title={isLooping ? t("loopOn") : t("loopOff")}>
                    <IconButton
                        size="small"
                        onClick={onToggleLoop}
                        sx={{
                            color: isLooping
                                ? accentBlue
                                : (isDark ? '#b3b9c6' : undefined),
                            backgroundColor: isLooping
                                ? (isDark ? 'rgba(41, 182, 246, 0.15)' : 'rgba(25, 118, 210, 0.1)')
                                : undefined,
                            border: isLooping ? `1px solid ${accentBlue}` : '1px solid transparent',
                            '&:hover': {
                                backgroundColor: isLooping
                                    ? (isDark ? 'rgba(41, 182, 246, 0.25)' : 'rgba(25, 118, 210, 0.2)')
                                    : undefined,
                            },
                        }}
                    >
                        <RepeatIcon fontSize="small" />
                    </IconButton>
                </Tooltip>

                {/* Right: speed selector + settings */}
                <Box sx={{ display: 'flex', alignItems: 'center', ml: 2, gap: 1 }}>
                    <Tooltip title={t("playbackSpeed")}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ color: isDark ? '#b3b9c6' : 'text.secondary' }}>
                                Speed:
                            </Typography>
                            <Select
                                value={playbackRate}
                                onChange={(e) => onPlaybackRateChange(Number(e.target.value))}
                                size="small"
                                variant="outlined"
                                sx={{
                                    minWidth: 70,
                                    '& .MuiSelect-select': {
                                        py: 0.25, fontSize: '0.8rem', fontFamily: monoFont,
                                        color: isDark ? '#fff' : undefined,
                                    },
                                    '& .MuiOutlinedInput-notchedOutline': {
                                        borderColor: isDark ? 'rgba(255,255,255,0.25)' : undefined,
                                    },
                                    '&:hover .MuiOutlinedInput-notchedOutline': {
                                        borderColor: isDark ? 'rgba(255,255,255,0.5)' : undefined,
                                    },
                                    '& .MuiSvgIcon-root': {
                                        color: isDark ? 'rgba(255,255,255,0.5)' : undefined,
                                    },
                                }}
                            >
                                {PLAYBACK_RATES.map((rate) => (
                                    <MenuItem key={rate} value={rate}>{rate}×</MenuItem>
                                ))}
                            </Select>
                        </Box>
                    </Tooltip>

                    {/* Sync info */}
                    <Tooltip title={t("syncInfo")}>
                        <IconButton
                            size="small"
                            onClick={() => setSyncInfoOpen((prev) => !prev)}
                            sx={{
                                color: syncInfoOpen
                                    ? (isDark ? '#ffcc80' : theme.palette.warning.dark)
                                    : (isDark ? 'rgba(255,255,255,0.3)' : theme.palette.text.disabled),
                                fontSize: '0.85rem',
                            }}
                        >
                            <InfoOutlinedIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                    </Tooltip>

                    {/* Settings gear */}
                    <Tooltip title={t("playbackSettings")}>
                        <IconButton
                            size="small"
                            onClick={(e) => setSettingsAnchor(e.currentTarget)}
                            sx={{
                                color: settingsOpen
                                    ? accentBlue
                                    : (isDark ? '#b3b9c6' : theme.palette.text.secondary),
                            }}
                        >
                            <SettingsIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Box>

            {/* Settings popover */}
            <Popover
                open={settingsOpen}
                anchorEl={settingsAnchor}
                onClose={() => setSettingsAnchor(null)}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                transformOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                slotProps={{
                    paper: {
                        sx: {
                            p: 2,
                            minWidth: 260,
                            backgroundColor: theme.palette.background.paper,
                            border: `1px solid ${theme.palette.divider}`,
                        },
                    },
                }}
            >
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600, color: theme.palette.text.primary }}>
                    Display Settings
                </Typography>

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={settings.showOverlays}
                            onChange={(e) => updateSetting('showOverlays', e.target.checked)}
                            size="small"
                            sx={{
                                color: isDark ? 'rgba(255,255,255,0.5)' : undefined,
                                '&.Mui-checked': { color: accentBlue },
                            }}
                        />
                    }
                    label={
                        <Typography variant="body2" sx={{ color: theme.palette.text.primary }}>
                            Show frame overlays
                        </Typography>
                    }
                    sx={{ mb: 1.5, ml: 0 }}
                />

                <Typography variant="caption" sx={{ mb: 0.75, display: 'block', color: theme.palette.text.secondary }}>
                    Timestamp format
                </Typography>
                <ToggleButtonGroup
                    value={settings.timestampFormat}
                    exclusive
                    onChange={(_, val) => { if (val) updateSetting('timestampFormat', val); }}
                    size="small"
                    fullWidth
                    sx={{
                        '& .MuiToggleButton-root': {
                            fontSize: '0.75rem',
                            fontFamily: monoFont,
                            py: 0.5,
                            color: isDark ? '#b3b9c6' : theme.palette.text.secondary,
                            borderColor: isDark ? 'rgba(255,255,255,0.2)' : theme.palette.divider,
                            '&.Mui-selected': {
                                color: '#fff',
                                backgroundColor: isDark ? 'rgba(41,182,246,0.25)' : theme.palette.primary.main,
                                borderColor: accentBlue,
                                '&:hover': {
                                    backgroundColor: isDark ? 'rgba(41,182,246,0.35)' : theme.palette.primary.dark,
                                },
                            },
                        },
                    }}
                >
                    <ToggleButton value="seconds">1.234s</ToggleButton>
                    <ToggleButton value="timecode">HH:MM:SS:FF</ToggleButton>
                </ToggleButtonGroup>
            </Popover>

            {/* Sync info panel */}
            <Collapse in={syncInfoOpen}>
                <Box
                    sx={{
                        px: 2,
                        py: 1,
                        mt: 0.5,
                        borderRadius: 1,
                        backgroundColor: isDark ? 'rgba(255, 204, 128, 0.06)' : 'rgba(255, 152, 0, 0.05)',
                        border: `1px solid ${isDark ? 'rgba(255, 204, 128, 0.15)' : 'rgba(255, 152, 0, 0.2)'}`,
                    }}
                >
                    <Typography
                        variant="caption"
                        sx={{
                            display: 'block',
                            color: isDark ? '#ffcc80' : theme.palette.warning.dark,
                            fontWeight: 600,
                            mb: 0.5,
                        }}
                    >
                        {t("syncInfoTitle")}
                    </Typography>
                    {/*<Typography*/}
                    {/*    variant="caption"*/}
                    {/*    sx={{*/}
                    {/*        display: 'block',*/}
                    {/*        color: theme.palette.text.secondary,*/}
                    {/*        lineHeight: 1.5,*/}
                    {/*    }}*/}
                    {/*>*/}
                    {/*    {t("syncInfoBody")}*/}
                    {/*</Typography>*/}
                </Box>
            </Collapse>
        </Box>
    );
};
