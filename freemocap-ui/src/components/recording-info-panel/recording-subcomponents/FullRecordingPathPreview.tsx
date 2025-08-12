// skellycam-ui/src/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview.tsx
import React from 'react';
import {Box, IconButton, Paper, Tooltip, Typography, useTheme} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import FolderSpecialIcon from '@mui/icons-material/FolderSpecial';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';

interface FullPathPreviewProps {
    directory: string;
    subfolder?: string;
    filename: string;
}

export const FullRecordingPathPreview: React.FC<FullPathPreviewProps> = ({
                                                                             directory,
                                                                             filename,
                                                                             subfolder
                                                                         }) => {
    const theme = useTheme();

    const parts = [
        {icon: <FolderIcon/>, text: directory},
        ...(subfolder ? [{icon: <FolderIcon/>, text: subfolder}] : []),
        {icon: <FolderSpecialIcon/>, text: filename}
    ];

    const fullPath = parts.map(p => p.text).join('/');

    // Get the directory path only (without the filename)
    const directoryToOpen = subfolder
        ? `${directory}/${subfolder}`
        : directory;

    const handleOpenFolder = async () => {
        try {
            await window.electronAPI.openFolder(directoryToOpen);
        } catch (error) {
            console.error('Failed to open folder:', error);
        }
    };

    return (
        <Paper
            elevation={0}
            sx={{
                p: 1.5,
                backgroundColor: theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.05)'
                    : 'rgba(0, 0, 0, 0.04)',
                borderRadius: 1,
                borderStyle: 'solid',
                borderColor: theme.palette.divider,
            }}
        >
            <Box sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 1
            }}>


                {/* Mobile/Narrow view */}
                <Box sx={{display: {xs: 'block', md: 'none'}}}>
                    <Tooltip title={fullPath} placement="bottom-start">
                        <Typography
                            noWrap
                            sx={{
                                fontFamily: 'monospace',
                                fontSize: '0.9rem',
                                cursor: 'pointer'
                            }}
                        >
                            {fullPath}
                        </Typography>
                    </Tooltip>
                </Box>

                {/* Desktop view */}
                <Box
                    sx={{
                        display: {xs: 'none', md: 'flex'},
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: 0.5
                    }}
                >
                    {parts.map((part, index) => (
                        <React.Fragment key={index}>
                            <Box sx={{
                                display: 'flex',
                                alignItems: 'center',
                                color: 'text.secondary',
                                // backgroundColor: 'background.paper',
                                borderRadius: 1,
                                px: 1,
                                py: 0.5,
                            }}>
                                {part.icon}
                                <Typography
                                    sx={{
                                        ml: 0.5,
                                        fontFamily: 'monospace',
                                        fontSize: '0.9rem'
                                    }}
                                >
                                    {part.text}
                                </Typography>
                            </Box>
                            {index < parts.length - 1 && (
                                <ChevronRightIcon sx={{color: 'text.secondary'}}/>
                            )}
                        </React.Fragment>
                    ))}
                </Box>

                <Tooltip title="Open folder in file explorer">
                    <IconButton
                        size="small"
                        onClick={handleOpenFolder}
                        sx={{
                            color: theme.palette.primary.contrastText,
                            '&:hover': {
                                backgroundColor: theme.palette.mode === 'dark'
                                    ? 'rgba(255, 255, 255, 0.08)'
                                    : 'rgba(0, 0, 0, 0.04)'
                            }
                        }}
                    >
                        <FolderOpenIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>
            </Box>

        </Paper>
    );
};
