import React from 'react';
import {Box, Slider, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useTheme} from '@mui/material';
import {ExposureMode} from "@/store/slices/cameras/cameras-types";

interface CameraConfigExposureProps {
    exposureMode: ExposureMode;
    exposure: number;
    onExposureModeChange: (mode: ExposureMode) => void;
    onExposureValueChange: (value: number) => void;
}

const ValueLabelComponent = (props: {
    children: React.ReactElement;
    value: number;
}) => {
    const { children, value } = props;

    return (
        <Tooltip title={
            <span>
                {`${(1000 / Math.pow(2, -1 * value)).toFixed(3)}ms (1/2`}
                <sup>{value}</sup>
                {` sec)`}
            </span>
        }>
            {children}
        </Tooltip>
    );
};

// Default constraints for exposure
const EXPOSURE_CONSTRAINTS = {
    min: -13,
    max: -4,
    default: -7
};

export const CameraConfigExposure: React.FC<CameraConfigExposureProps> = ({
                                                                              exposureMode = 'MANUAL',
                                                                              exposure = EXPOSURE_CONSTRAINTS.default,
                                                                              onExposureModeChange,
                                                                              onExposureValueChange
                                                                          }) => {
    const theme = useTheme();

    const handleModeChange = (
        event: React.MouseEvent<HTMLElement>,
        newMode: string | null,
    ): void => {
        if (newMode !== null) {
            onExposureModeChange(newMode as ExposureMode);
        }
    };

    const handleSliderChange = (event: Event, value: number | number[]): void => {
        onExposureValueChange(value as number);
    };

    const baseMarks = [
        { value: EXPOSURE_CONSTRAINTS.min, label: String(EXPOSURE_CONSTRAINTS.min) },
        {
            value: EXPOSURE_CONSTRAINTS.default,
            label: `${EXPOSURE_CONSTRAINTS.default} (default)`
        },
        { value: EXPOSURE_CONSTRAINTS.max, label: String(EXPOSURE_CONSTRAINTS.max) }
    ];

    const marks = [
        ...baseMarks,
        ...(![
                EXPOSURE_CONSTRAINTS.min as number,
                EXPOSURE_CONSTRAINTS.default as number,
                EXPOSURE_CONSTRAINTS.max as number
            ].includes(exposure)
                ? [{
                    value: exposure,
                    label: `${exposure}`,
                }]
                : []
        )
    ].sort((a, b) => a.value - b.value);

    return (
        <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
                Camera Exposure
            </Typography>
            <Tooltip title="Choose between automatic or manual exposure control">
                <ToggleButtonGroup
                    color={theme.palette.primary.main as any}
                    value={exposureMode}
                    exclusive
                    onChange={handleModeChange}
                    size="small"
                    sx={{
                        '& .MuiToggleButton-root.Mui-selected': {
                            backgroundColor: theme.palette.primary.main,
                            border: `1px solid ${theme.palette.text.secondary}`,
                            color: theme.palette.primary.contrastText,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.light,
                            },
                        }
                    }}
                >
                    <ToggleButton value="MANUAL">Manual</ToggleButton>
                    <ToggleButton value="AUTO">Auto</ToggleButton>
                    <ToggleButton value="RECOMMEND">Recommend</ToggleButton>
                </ToggleButtonGroup>
            </Tooltip>
            <Tooltip title="Adjust exposure time, e.g. cv2.VideoCapture.set(cv2.CAP_PROP_EXPOSURE, value)">
                <Box sx={{ flexGrow: 1 }}>
                    <Slider
                        value={exposure}
                        disabled={exposureMode === 'AUTO' || exposureMode === 'RECOMMEND'}
                        min={EXPOSURE_CONSTRAINTS.min}
                        max={EXPOSURE_CONSTRAINTS.max}
                        step={1}
                        marks={marks}
                        valueLabelDisplay="auto"
                        onChange={handleSliderChange}
                        components={{
                            ValueLabel: ValueLabelComponent
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
            </Tooltip>
        </Box>
    );
};
