import React, { useState } from 'react';
import IconButton from '@mui/material/IconButton';
import SettingsIcon from '@mui/icons-material/Settings';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { useTheme } from "@mui/material/styles";
import { ImageScaleSlider } from './ImageScaleSlider';

export const CamerasViewSettingsOverlay = () => {
    const [expanded, setExpanded] = useState(false);
    const [scale, setScale] = useState(0.5);
    const theme = useTheme();

    return (
        <Box
            sx={{
                position: 'absolute',
                top: 16,
                right: 16,
                zIndex: 1000,
            }}
        >
            <IconButton onClick={() => setExpanded(!expanded)}>
                <SettingsIcon />
            </IconButton>
            {expanded && (
                <Paper
                    sx={{
                        p: 2,
                        mt: 1,
                        width: 300, // Fixed width for the expanded box
                        position: 'relative', // Ensure the gear icon stays pinned
                    }}
                >
                    <ImageScaleSlider scale={scale} onScaleChange={setScale} />
                </Paper>
            )}
        </Box>
    );
};
