import {useLocation, useNavigate} from "react-router-dom";
import {useCallback, useMemo} from "react";
import {alpha, darken} from "@mui/material/styles";
import {Box, Chip, Link, Tab, Tabs, Tooltip, Typography} from "@mui/material";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import {useAppDispatch, useAppSelector} from "@/store";
import {
    activeRecordingCleared,
    selectActiveRecordingFullPath,
    selectActiveRecordingName,
} from "@/store/slices/active-recording/active-recording-slice";
import {selectPlannedRecordingName} from "@/store/slices/recording";
import {useElectronIPC} from "@/services";

const NAV_TABS = [
    {path: '/welcome', label: 'Home'},
    {path: '/streaming', label: 'Streaming'},
    {path: '/playback', label: 'Playback'},
    {path: '/browse', label: 'Recordings'},
    {path: '/active-recording', label: 'Active Recording'},
] as const;

const MONO_FONT = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';

const ActiveRecordingTabLabel: React.FC<{isActive: boolean}> = ({isActive}) => {
    const dispatch = useAppDispatch();
    const recordingName = useAppSelector(selectActiveRecordingName);
    const fullPath = useAppSelector(selectActiveRecordingFullPath);
    const plannedName = useAppSelector(selectPlannedRecordingName);
    const {api} = useElectronIPC();

    const handleOpenFolder = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!fullPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({path: fullPath});
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    };

    const handleClearRecording = (e: React.MouseEvent) => {
        e.stopPropagation();
        dispatch(activeRecordingCleared());
    };

    const tooltipContent = fullPath ? (
        <Box sx={{p: 0.5}}>
            <Typography variant="caption" sx={{fontFamily: MONO_FONT, display: 'block', mb: 0.5}}>
                {fullPath}
            </Typography>
            <Link
                component="button"
                onClick={handleOpenFolder}
                underline="hover"
                sx={{display: 'inline-flex', alignItems: 'center', gap: 0.5, fontSize: '0.7rem'}}
            >
                <FolderOpenIcon sx={{fontSize: 14}}/>
                Open in Explorer
            </Link>
        </Box>
    ) : plannedName ? (
        <Typography variant="caption">No active recording — will record as <strong>{plannedName}</strong></Typography>
    ) : (
        <Typography variant="caption">No active recording</Typography>
    );

    return (
        <Tooltip title={tooltipContent} placement="bottom" arrow>
            <Box sx={{display: 'inline-flex', alignItems: 'center', gap: 0.75}}>
                <Typography component="span" sx={{fontSize: 'inherit'}}>Active Recording</Typography>
                {recordingName ? (
                    <Chip
                        size="small"
                        label={recordingName}
                        onDelete={handleClearRecording}
                        sx={{
                            height: 18,
                            fontSize: '0.65rem',
                            fontFamily: MONO_FONT,
                            maxWidth: 220,
                            '& .MuiChip-label': {
                                px: 0.75,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                            },
                            '& .MuiChip-deleteIcon': {
                                fontSize: 12,
                                opacity: 0,
                                transition: 'opacity 0.15s',
                            },
                            '&:hover .MuiChip-deleteIcon': {opacity: 1},
                        }}
                    />
                ) : plannedName ? (
                    <Chip
                        size="small"
                        label={plannedName}
                        variant="outlined"
                        sx={{
                            height: 18,
                            fontSize: '0.65rem',
                            fontFamily: MONO_FONT,
                            maxWidth: 220,
                            opacity: 0.55,
                            borderStyle: 'dashed',
                            '& .MuiChip-label': {
                                px: 0.75,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                            },
                        }}
                    />
                ) : (
                    <Typography
                        component="span"
                        sx={{fontSize: '0.65rem', color: 'text.disabled', fontStyle: 'italic'}}
                    >
                        (none)
                    </Typography>
                )}
            </Box>
        </Tooltip>
    );
};

export const MainNavTabs = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const activeTab = useMemo(() => {
        const idx = NAV_TABS.findIndex(t => location.pathname === t.path);
        return idx >= 0 ? idx : 0;
    }, [location.pathname]);

    const handleTabChange = useCallback((_: React.SyntheticEvent, index: number) => {
        navigate(NAV_TABS[index].path);
    }, [navigate]);

    return (
        <Tabs
            value={activeTab}
            onChange={handleTabChange}
            sx={(theme) => ({
                minHeight: 28,
                px: 0.5,
                borderRadius: 1,
                backgroundColor: darken(theme.palette.background.default, 0.2),
                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                '& .MuiTab-root': {
                    minHeight: 28,
                    fontSize: '0.75rem',
                    py: 0.5,
                    borderRadius: 0.75,
                    position: 'relative',
                    textTransform: 'none',
                },
                '& .MuiTab-root:not(:last-of-type)::after': {
                    content: '""',
                    position: 'absolute',
                    right: 0,
                    top: '22%',
                    height: '56%',
                    borderRight: `1px solid ${alpha(theme.palette.divider, 0.15)}`,
                },
                '& .MuiTab-root.Mui-selected': {
                    backgroundColor: darken(theme.palette.background.paper, 0.15),
                },
            })}
        >
            {NAV_TABS.map((tab, idx) => {
                const isActive = idx === activeTab;
                const label = tab.path === '/active-recording'
                    ? <ActiveRecordingTabLabel isActive={isActive}/>
                    : tab.label;
                return <Tab key={tab.path} label={label}/>;
            })}
        </Tabs>
    );
};
