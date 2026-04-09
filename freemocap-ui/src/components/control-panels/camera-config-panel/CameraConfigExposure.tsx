import React from 'react';
import {Box, Slider, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useTheme} from '@mui/material';
import {ExposureMode} from "@/store/slices/cameras/cameras-types";
import {useTranslation} from 'react-i18next';

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
    const { t } = useTranslation();

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
            {/* Label and mode toggle on the same line */}
            <Box sx={{display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5}}>
                <Typography variant="body2" color="text.secondary" sx={{whiteSpace: 'nowrap', fontSize: 12}}>
                    {t("exposure")}
                </Typography>
                <Tooltip title={t("exposureControl")}>
                    <ToggleButtonGroup
                        color={theme.palette.primary.main as any}
                        value={exposureMode}
                        exclusive
                        onChange={handleModeChange}
                        size="small"
                        sx={{
                            '& .MuiToggleButton-root': {
                                py: 0.25,
                                px: 1,
                                fontSize: 11,
                            },
                            '& .MuiToggleButton-root.Mui-selected': {
                                backgroundColor: theme.palette.primary.dark,
                                border: `1px solid ${theme.palette.text.secondary}`,
                                color: theme.palette.primary.contrastText,
                                '&:hover': {
                                    backgroundColor: theme.palette.primary.light,
                                },
                            }
                        }}
                    >
                        <ToggleButton value="MANUAL">{t("manual")}</ToggleButton>
                        <ToggleButton value="AUTO">{t("auto")}</ToggleButton>
                        <ToggleButton value="RECOMMEND">{t("recommend")}</ToggleButton>
                    </ToggleButtonGroup>
                </Tooltip>
            </Box>
            <Tooltip title={t("adjustExposure")}>
                <Box sx={{px: 1}}>
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
                            '& .MuiSlider-markLabel': {
                                fontSize: 11,
                            },
                            '& .MuiSlider-thumb': {
                                width: 16,
                                height: 16,
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
