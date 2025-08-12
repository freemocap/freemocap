// CameraConfigExposure.tsx
import * as React from 'react';
import {Box, Slider, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useTheme} from '@mui/material';
import {CAMERA_DEFAULT_CONSTRAINTS, ExposureMode} from "@/store/slices/cameras-slices/camera-types";
import {useAppDispatch} from "@/store/AppStateStore";

interface CameraConfigExposureProps {
    exposureMode: ExposureMode;
    exposure: number ;
    onExposureModeChange: (mode: ExposureMode) => void;
    onExposureValueChange: (value: number) => void;
}

const ValueLabelComponent = (props: {
    children: React.ReactElement;
    value: number;
}) => {
    const {children, value} = props;

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
export const CameraConfigExposure: React.FC<CameraConfigExposureProps> = ({
                                                                              exposureMode = CAMERA_DEFAULT_CONSTRAINTS.exposure_modes[0], // MANUAL
                                                                              exposure = CAMERA_DEFAULT_CONSTRAINTS.exposure.default,
                                                                              onExposureModeChange,
                                                                              onExposureValueChange
                                                                          }) => {
    const theme = useTheme();

    const handleModeChange = (
        event: React.MouseEvent<HTMLElement>,
        newMode: string,
    ) => {
        if (newMode !== null) {
            onExposureModeChange(newMode as ExposureMode);
        }
    };



    const baseMarks = [
        {value: CAMERA_DEFAULT_CONSTRAINTS.exposure.min, label: String(CAMERA_DEFAULT_CONSTRAINTS.exposure.min)},
        {value: CAMERA_DEFAULT_CONSTRAINTS.exposure.default, label: `${CAMERA_DEFAULT_CONSTRAINTS.exposure.default} (default)`},
        {value: CAMERA_DEFAULT_CONSTRAINTS.exposure.max, label: String(CAMERA_DEFAULT_CONSTRAINTS.exposure.max)}
    ];
    const marks = [
        ...baseMarks,
        ...(![CAMERA_DEFAULT_CONSTRAINTS.exposure.min as number,
                CAMERA_DEFAULT_CONSTRAINTS.exposure.default as number,
                CAMERA_DEFAULT_CONSTRAINTS.exposure.max as number].includes(exposure)
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
                <Box sx={{flexGrow: 1}}>
                    <Slider
                        value={exposure}
                        disabled={exposureMode === 'AUTO' || exposureMode === 'RECOMMEND'}
                        min={CAMERA_DEFAULT_CONSTRAINTS.exposure.min}
                        max={CAMERA_DEFAULT_CONSTRAINTS.exposure.max}
                        step={1}
                        marks={marks}
                        valueLabelDisplay="auto"
                        onChange={(_, value) => onExposureValueChange(value as number)}
                        components={{
                            ValueLabel: ValueLabelComponent
                        }}
                        sx={{
                            color: theme.palette.primary.light,
                            '& .MuiSlider-thumb': {
                                '&:hover, &.Mui-focusVisible': {
                                    boxShadow: `0px 0px 0px 8px ${theme.palette.primary.light}33`, // Adding a cool effect on hover and focus
                                },
                            },

                        }}
                    />
                </Box>
            </Tooltip>
        </Box>
    );
};

