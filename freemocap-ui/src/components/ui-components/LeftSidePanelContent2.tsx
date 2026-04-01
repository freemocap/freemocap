// freemocap-ui/src/components/ui-components/LeftSidePanelContent.tsx
import * as React from 'react';
import Box from "@mui/material/Box";
import {Button, IconButton, List, ListItem, Tooltip, useTheme} from "@mui/material";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";
import ThemeToggle from "@/components/ui-components/ThemeToggle";
import HomeIcon from '@mui/icons-material/Home';
import MenuIcon from '@mui/icons-material/Menu';
import MenuOpenIcon from '@mui/icons-material/MenuOpen';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import StopIcon from '@mui/icons-material/Stop';
import VideocamIcon from '@mui/icons-material/Videocam';
import SlideshowIcon from '@mui/icons-material/Slideshow';
import SettingsIcon from '@mui/icons-material/Settings';
import {useLocation, useNavigate} from "react-router-dom";
import {CameraConfigTreeView} from "@/components/camera-config-tree-view/CameraConfigTreeView";
import {ServerConnectionStatus} from "@/components/ServerConnectionStatus";
import {useAppDispatch, useAppSelector} from "@/store";
import {startRecording, stopRecording} from "@/store";
import {useTranslation} from "react-i18next";
import {useServer} from "@/services/server/ServerContextProvider";
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import {MicrophoneSelector} from "@/components/recording-info-panel/recording-subcomponents/MicrophoneSelector";
import {useElectronIPC} from "@/services";
import {useState} from "react";
import {getTimestampString} from "@/components/recording-info-panel/getTimestampString";

interface LeftSidePanelContentProps {
    isCollapsed: boolean;
    onToggleCollapse: () => void;
}

// Scrollbar styles
const scrollbarStyles = {
    '&::-webkit-scrollbar': {
        width: '6px',
        backgroundColor: 'transparent',
    },
    '&::-webkit-scrollbar-thumb': {
        backgroundColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
            ? 'rgba(255, 255, 255, 0.2)'
            : 'rgba(0, 0, 0, 0.2)',
        borderRadius: '3px',
        '&:hover': {
            backgroundColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
                ? 'rgba(255, 255, 255, 0.3)'
                : 'rgba(0, 0, 0, 0.3)',
        },
    },
    '&::-webkit-scrollbar-track': {
        backgroundColor: 'transparent',
    },
    scrollbarWidth: 'thin',
    scrollbarColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.2) transparent'
        : 'rgba(0, 0, 0, 0.2) transparent',
};

/** Collapsed sidebar: vertical icon toolbar with hamburger, record, and cameras. */
const CollapsedToolbar: React.FC<{
    onToggleCollapse: () => void;
    isRecording: boolean;
    noCameras: boolean;
    onRecordClick: () => void;
}> = ({onToggleCollapse, isRecording, noCameras, onRecordClick}) => {
    const theme = useTheme();
    const navigate = useNavigate();
    const location = useLocation();
    const {t} = useTranslation();

    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            backgroundColor: theme.palette.mode === 'dark'
                ? theme.palette.background.paper
                : theme.palette.grey[50],
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            pt: 0.5,
            gap: 0.5,
        }}>
            {/* Hamburger to expand */}
            <Tooltip title={t('expandSidebar')} placement="right">
                <IconButton size="small" onClick={onToggleCollapse} sx={{color: theme.palette.text.primary}}>
                    <MenuIcon fontSize="small"/>
                </IconButton>
            </Tooltip>

            {/* Record button */}
            <Tooltip title={isRecording ? t('stopRecording') : t('startRecording')} placement="right">
                <span>
                <IconButton
                    size="small"
                    onClick={onRecordClick}
                    disabled={noCameras && !isRecording}
                    sx={{
                        color: isRecording ? '#fb1402' : theme.palette.text.secondary,
                        animation: isRecording ? 'pulse-record 2s infinite' : 'none',
                        '@keyframes pulse-record': {
                            '0%, 100%': {color: '#fb1402'},
                            '50%': {color: '#711c1c'},
                        },
                    }}
                >
                    {isRecording ? <StopIcon fontSize="small"/> : <FiberManualRecordIcon fontSize="small"/>}
                </IconButton>
                </span>
            </Tooltip>

            {/* Cameras page */}
            <Tooltip title={t('cameras')} placement="right">
                <IconButton
                    size="small"
                    onClick={() => navigate('/cameras')}
                    sx={{
                        color: location.pathname === '/cameras'
                            ? theme.palette.success.main
                            : theme.palette.text.secondary,
                    }}
                >
                    <VideocamIcon fontSize="small"/>
                </IconButton>
            </Tooltip>

            {/* Videos page */}
            <Tooltip title={t('videos')} placement="right">
                <IconButton
                    size="small"
                    onClick={() => navigate('/playback')}
                    sx={{
                        color: location.pathname === '/playback'
                            ? theme.palette.success.main
                            : theme.palette.text.secondary,
                    }}
                >
                    <SlideshowIcon fontSize="small"/>
                </IconButton>
            </Tooltip>

            {/* Spacer */}
            <Box sx={{flex: 1}}/>

            {/* Settings page */}
            <Tooltip title={t('settings')} placement="right">
                <IconButton
                    size="small"
                    onClick={() => navigate('/settings')}
                    sx={{
                        color: location.pathname === '/settings'
                            ? theme.palette.success.main
                            : theme.palette.text.secondary,
                        mb: 0.5,
                    }}
                >
                    <SettingsIcon fontSize="small"/>
                </IconButton>
            </Tooltip>
        </Box>
    );
};

export const LeftSidePanelContent2: React.FC<LeftSidePanelContentProps> = ({
                                                                              isCollapsed,
                                                                              onToggleCollapse,
                                                                          }) => {
    const theme = useTheme();
    const navigate = useNavigate();
    const location = useLocation();
    const dispatch = useAppDispatch();
    const {t} = useTranslation();

    const recordingInfo = useAppSelector((state) => state.recording);
    const isRecording = recordingInfo.isRecording;
    const {connectedCameraIds} = useServer();
    const noCameras = connectedCameraIds.length === 0;
    const [micDeviceIndex, setMicDeviceIndex] = useState<number>(-1);

    const handleCollapsedRecordClick = async (): Promise<void> => {
        if (isRecording) {
            await dispatch(stopRecording()).unwrap();
        } else {
            // Quick-start recording with timestamp-based defaults
            const recordingName = getTimestampString();
            await dispatch(startRecording({
                recordingName,
                recordingDirectory: recordingInfo.recordingDirectory,
                micDeviceIndex,
            })).unwrap();
        }
    };

    const navButtonSx = (isActive: boolean) => ({
        padding: '4px',
        color: isActive ? theme.palette.success.main : theme.palette.text.secondary,
        '&:hover': {
            color: theme.palette.success.main,
            backgroundColor: theme.palette.action.hover,
        },
    });

    // Collapsed: show vertical icon toolbar
    if (isCollapsed) {
        return (
            <CollapsedToolbar
                onToggleCollapse={onToggleCollapse}
                isRecording={isRecording}
                noCameras={noCameras}
                onRecordClick={handleCollapsedRecordClick}
            />
        );
    }

    // Expanded: full sidebar content
    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            backgroundColor: theme.palette.mode === 'dark'
                ? theme.palette.background.paper
                : theme.palette.grey[50],
            color: theme.palette.text.primary,
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto',
            overflowX: 'hidden',
            ...scrollbarStyles
        }}>
            {/* Header — single row with hamburger, title, nav icons */}
            <List disablePadding>
                <ListItem
                    sx={{
                        borderBottom: theme.palette.mode === 'dark'
                            ? '1px solid rgba(255,255,255,0.08)'
                            : '1px solid rgba(0,0,0,0.08)',
                        py: 0.5,
                        px: 0.5,
                        minHeight: 40,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 0.25,
                        overflow: 'hidden',
                    }}
                >
                    {/* Hamburger to collapse */}
                    <Tooltip title={t('collapseSidebar')}>
                        <IconButton size="small" onClick={onToggleCollapse}
                                    sx={{color: theme.palette.text.primary, flexShrink: 0}}>
                            <MenuOpenIcon fontSize="small"/>
                        </IconButton>
                    </Tooltip>

                    {/* Title — truncates when narrow */}
                    <Box
                        component="span"
                        sx={{
                            fontSize: 14,
                            fontWeight: 600,
                            color: theme.palette.text.primary,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            minWidth: 0,
                            flexShrink: 1,
                            flexGrow: 1,
                        }}
                    >
                        FreeMoCap 💀✨
                    </Box>

                    {/* Nav icons — fixed row, never wraps */}
                    <Box sx={{display: 'flex', alignItems: 'center', gap: 0.25, flexShrink: 0}}>
                        <Tooltip title={t('home')}>
                            <IconButton
                                size="small"
                                onClick={() => navigate('/')}
                                sx={navButtonSx(location.pathname === '/')}
                            >
                                <HomeIcon sx={{fontSize: 18}}/>
                            </IconButton>
                        </Tooltip>

                        <Tooltip title={t('settings')}>
                            <IconButton
                                size="small"
                                onClick={() => navigate('/settings')}
                                sx={navButtonSx(location.pathname === '/settings')}
                            >
                                <SettingsIcon sx={{fontSize: 18}}/>
                            </IconButton>
                        </Tooltip>

                        <ThemeToggle/>
                    </Box>
                </ListItem>
            </List>
            {/* Server Settings */}
            <ServerConnectionStatus/>
            {/* Prominent Cameras / Playback page toggle */}
            <Box sx={{
                display: 'flex',
                gap: 0.5,
                px: 0.75,
                py: 0.75,
                borderBottom: theme.palette.mode === 'dark'
                    ? '1px solid rgba(255,255,255,0.08)'
                    : '1px solid rgba(0,0,0,0.08)',
            }}>
                <Button
                    variant={location.pathname === '/cameras' ? 'contained' : 'outlined'}
                    size="small"
                    startIcon={<VideocamIcon sx={{fontSize: 16}}/>}
                    onClick={() => navigate('/cameras')}
                    fullWidth
                    sx={{
                        textTransform: 'none',
                        fontWeight: 600,
                        fontSize: '0.8rem',
                        py: 0.75,
                        ...(location.pathname === '/cameras' ? {
                            backgroundColor: theme.palette.success.main,
                            color: '#fff',
                            '&:hover': {backgroundColor: theme.palette.success.dark},
                        } : {
                            borderColor: theme.palette.divider,
                            color: theme.palette.text.secondary,
                            '&:hover': {
                                borderColor: theme.palette.success.main,
                                color: theme.palette.success.main,
                                backgroundColor: theme.palette.mode === 'dark'
                                    ? 'rgba(76,175,80,0.08)'
                                    : 'rgba(76,175,80,0.04)',
                            },
                        }),
                    }}
                >
                    {t('cameras')}
                </Button>
                <Button
                    variant={location.pathname === '/playback' ? 'contained' : 'outlined'}
                    size="small"
                    startIcon={<SlideshowIcon sx={{fontSize: 16}}/>}
                    onClick={() => navigate('/playback')}
                    fullWidth
                    sx={{
                        textTransform: 'none',
                        fontWeight: 600,
                        fontSize: '0.8rem',
                        py: 0.75,
                        ...(location.pathname === '/playback' ? {
                            backgroundColor: theme.palette.info.main,
                            color: '#fff',
                            '&:hover': {backgroundColor: theme.palette.info.dark},
                        } : {
                            borderColor: theme.palette.divider,
                            color: theme.palette.text.secondary,
                            '&:hover': {
                                borderColor: theme.palette.info.main,
                                color: theme.palette.info.main,
                                backgroundColor: theme.palette.mode === 'dark'
                                    ? 'rgba(41,182,246,0.08)'
                                    : 'rgba(41,182,246,0.04)',
                            },
                        }),
                    }}
                >
                    {t('videoPlayback')}
                </Button>
            </Box>


            {/* Main Content Area */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5,
                pt: 0.5,
                pb: 2,
            }}>
                <RecordingInfoPanel/>
                <CameraConfigTreeView/>
            </Box>
        </Box>
    );
};
