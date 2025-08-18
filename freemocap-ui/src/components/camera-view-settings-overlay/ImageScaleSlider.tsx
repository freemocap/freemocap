import React, { useState } from 'react';
import { Box, Slider, Tooltip, Typography, useTheme } from '@mui/material';

interface ImageScaleSliderProps {
    scale: number;
    onScaleChange: (value: number) => void;
}

const ValueLabelComponent = (props: {
    children: React.ReactElement;
    value: number;
}) => {
    const { children, value } = props;

    return (
        <Tooltip title={
            <span>
                {`Scale: ${value.toFixed(1)}`}
            </span>
        }>
            {children}
        </Tooltip>
    );
};

export const ImageScaleSlider: React.FC<ImageScaleSliderProps> = ({
    scale = 0.5,
    onScaleChange,
}) => {
    const theme = useTheme();

    const marks = [
        { value: 0.1, label: '0.1' },
        { value: 0.5, label: '0.5 (default)' },
        { value: 2.0, label: '2.0' },
    ];

    return (
        <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
                Image Scale
            </Typography>
            <Slider
                value={scale}
                min={0.1}
                max={2.0}
                step={0.1}
                marks={marks}
                valueLabelDisplay="auto"
                onChange={(_, value) => onScaleChange(value as number)}
                components={{
                    ValueLabel: ValueLabelComponent,
                }}
                sx={{
                    color: theme.palette.primary.light,
                    '& .MuiSlider-thumb': {
                        '&:hover, &.Mui-focusVisible': {
                            boxShadow: `0px 0px 0px 8px ${theme.palette.primary.light}33`,
                        },
                    },
                }}
            />
        </Box>
    );
};