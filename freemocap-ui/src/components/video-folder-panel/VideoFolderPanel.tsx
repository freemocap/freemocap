// freemocap-ui/src/components/video-folder-panel/VideoFolderPanel.tsx
import React, {useState} from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    alpha,
    Box,
    Button,
    Checkbox,
    FormControlLabel,
    IconButton,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Paper,
    Stack,
    TextField,
    Tooltip,
    Typography,
    useTheme
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import VideoFileIcon from '@mui/icons-material/VideoFile';
// Updated imports - using the videos thunks and selectors from the store barrel export
import {loadVideos, openVideoFile, selectVideoLoadFolder, useAppDispatch, useAppSelector} from "@/store";

export const VideoFolderPanel: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    // Updated selectors to match the store structure
    const videoFolder = useAppSelector(state => state.videos.folder);
    const videoFiles = useAppSelector(state => state.videos.files);
    const isLoading = useAppSelector(state => state.videos.isLoading);
    const error = useAppSelector(state => state.videos.error);

    const [showSettings, setShowSettings] = useState(false);
    const [selectedVideos, setSelectedVideos] = useState<string[]>([]);
    const [filterText, setFilterText] = useState('');

    const handleSelectFolder = async () => {
        dispatch(selectVideoLoadFolder());
        setSelectedVideos([]);
    };

    const handleLoadVideos = () => {
        if (videoFiles.length === 0) return;

        const filesToLoad = selectedVideos.length > 0
            ? videoFiles.filter(file => selectedVideos.includes(file.path))
            : videoFiles;
        dispatch(loadVideos({folder: videoFolder, files: filesToLoad}));
    };

    const handleVideoSelect = (path: string) => {
        setSelectedVideos(prev => prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path]);
    };

    const handleSelectAll = () => {
        setSelectedVideos(prev => prev.length === filteredVideos.length ? [] : filteredVideos.map(file => file.path));
    };

    const handleOpenVideo = (path: string) => {
        dispatch(openVideoFile(path));
    };

    const filteredVideos = videoFiles.filter(file =>
        file.name.toLowerCase().includes(filterText.toLowerCase())
    );

    return (
        <Accordion
            defaultExpanded
            sx={{
                borderRadius: 2,
                '&:before': {display: 'none'},
                boxShadow: theme.shadows[3]
            }}
        >
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                backgroundColor: theme.palette.primary.main,
                borderTopLeftRadius: 8,
                borderTopRightRadius: 8,
            }}>
                <AccordionSummary
                    expandIcon={<ExpandMoreIcon sx={{color: theme.palette.primary.contrastText}}/>}
                    sx={{
                        flex: 1,
                        color: theme.palette.primary.contrastText,
                        '&:hover': {
                            backgroundColor: theme.palette.primary.light,
                        }
                    }}
                >
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <VideoLibraryIcon/>
                        <Typography variant="subtitle1" fontWeight="medium">
                            Video Folder Selection
                        </Typography>
                    </Stack>
                </AccordionSummary>

                <Box sx={{pr: 2}}>
                    <Button
                        variant="contained"
                        color="secondary"
                        disabled={videoFiles.length === 0 || isLoading || (selectedVideos.length === 0 && videoFiles.length > 0)}
                        onClick={handleLoadVideos}
                        startIcon={<PlayArrowIcon/>}
                        sx={{minWidth: '120px'}}
                    >
                        Load Videos
                    </Button>
                </Box>

                <Box sx={{pr: 2}}>
                    <IconButton
                        onClick={() => setShowSettings(!showSettings)}
                        sx={{
                            color: showSettings
                                ? theme.palette.primary.contrastText
                                : alpha(theme.palette.primary.contrastText, 0.7)
                        }}
                    >
                        <SettingsIcon/>
                    </IconButton>
                </Box>
            </Box>

            <AccordionDetails sx={{p: 2, bgcolor: 'background.default'}}>
                <Paper
                    elevation={0}
                    sx={{
                        bgcolor: 'background.paper',
                        borderRadius: 2,
                        overflow: 'hidden',
                        p: 2
                    }}
                >
                    <Stack spacing={2}>
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                            <TextField
                                fullWidth
                                label="Video Folder Path"
                                variant="outlined"
                                value={videoFolder}
                                InputProps={{
                                    readOnly: true,
                                }}
                                disabled={isLoading}
                            />
                            <Button
                                variant="outlined"
                                startIcon={<FolderOpenIcon/>}
                                onClick={handleSelectFolder}
                                disabled={isLoading}
                            >
                                Browse
                            </Button>
                        </Box>

                        {error && (
                            <Typography color="error" variant="body2">
                                Error: {error}
                            </Typography>
                        )}

                        {videoFiles.length > 0 && (
                            <Box>
                                <Box sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    mb: 1
                                }}>
                                    <Typography variant="subtitle2">
                                        Found {videoFiles.length} video files
                                        {filterText && ` (${filteredVideos.length} shown)`}:
                                    </Typography>

                                    <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                                        <TextField
                                            size="small"
                                            placeholder="Filter videos..."
                                            value={filterText}
                                            onChange={(e) => setFilterText(e.target.value)}
                                            sx={{width: '200px'}}
                                        />
                                        <FormControlLabel
                                            control={
                                                <Checkbox
                                                    checked={selectedVideos.length === filteredVideos.length && filteredVideos.length > 0}
                                                    indeterminate={selectedVideos.length > 0 && selectedVideos.length < filteredVideos.length}
                                                    onChange={handleSelectAll}
                                                    disabled={filteredVideos.length === 0}
                                                />
                                            }
                                            label="Select All"
                                        />
                                    </Box>
                                </Box>

                                <Paper
                                    variant="outlined"
                                    sx={{
                                        maxHeight: '200px',
                                        overflow: 'auto',
                                        p: 0,
                                    }}
                                >
                                    <List dense disablePadding>
                                        {filteredVideos.map((file) => (
                                            <ListItem
                                                key={file.path}
                                                disablePadding
                                                secondaryAction={
                                                    <Tooltip title="Open video">
                                                        <IconButton
                                                            edge="end"
                                                            size="small"
                                                            onClick={() => handleOpenVideo(file.path)}
                                                        >
                                                            <PlayArrowIcon/>
                                                        </IconButton>
                                                    </Tooltip>
                                                }
                                            >
                                                <ListItemButton
                                                    dense
                                                    onClick={() => handleVideoSelect(file.path)}
                                                    selected={selectedVideos.includes(file.path)}
                                                >
                                                    <ListItemIcon sx={{minWidth: 36}}>
                                                        <Checkbox
                                                            edge="start"
                                                            checked={selectedVideos.includes(file.path)}
                                                            tabIndex={-1}
                                                            disableRipple
                                                        />
                                                    </ListItemIcon>
                                                    <ListItemIcon sx={{minWidth: 36}}>
                                                        <VideoFileIcon fontSize="small"/>
                                                    </ListItemIcon>
                                                    <ListItemText
                                                        primary={file.name}
                                                        primaryTypographyProps={{
                                                            variant: 'body2',
                                                            sx: {fontFamily: 'monospace'}
                                                        }}
                                                    />
                                                </ListItemButton>
                                            </ListItem>
                                        ))}
                                    </List>
                                </Paper>
                            </Box>
                        )}

                        {showSettings && (
                            <Paper
                                variant="outlined"
                                sx={{p: 2}}
                            >
                                <Typography variant="subtitle2" gutterBottom>
                                    Video Loading Settings
                                </Typography>
                                <Typography variant="body2" color="text.secondary" gutterBottom>
                                    Configure how videos are loaded and processed.
                                </Typography>

                                <Stack spacing={1} sx={{mt: 1}}>
                                    <FormControlLabel
                                        control={<Checkbox defaultChecked/>}
                                        label="Automatically synchronize videos"
                                    />
                                    <FormControlLabel
                                        control={<Checkbox/>}
                                        label="Extract frames on load"
                                    />
                                    <FormControlLabel
                                        control={<Checkbox/>}
                                        label="Generate thumbnails"
                                    />
                                </Stack>
                            </Paper>
                        )}
                    </Stack>
                </Paper>
            </AccordionDetails>
        </Accordion>
    );
};
