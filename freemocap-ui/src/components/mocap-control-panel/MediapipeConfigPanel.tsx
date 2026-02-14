import React, {useCallback} from "react";
import {
    Box,
    Chip,
    FormControl,
    FormControlLabel,
    InputLabel,
    MenuItem,
    Select,
    Slider,
    Stack,
    Switch,
    Typography,
    useTheme,
} from "@mui/material";
import {useMocap} from "@/hooks/useMocap";
import {
    MEDIAPIPE_REALTIME_PRESET,
    MEDIAPIPE_POSTHOC_PRESET,
    MediapipeModelComplexity,
} from "@/store/slices/mocap";

const MODEL_COMPLEXITY_LABELS: Record<MediapipeModelComplexity, string> = {
    0: "Lite (fastest)",
    1: "Full (balanced)",
    2: "Heavy (most accurate)",
};

type DetectorPreset = "realtime" | "posthoc" | "custom";

function detectPreset(
    config: { model_complexity: number; enable_segmentation: boolean; smooth_segmentation: boolean }
): DetectorPreset {
    if (
        config.model_complexity === 0 &&
        !config.enable_segmentation &&
        !config.smooth_segmentation
    ) return "realtime";
    if (
        config.model_complexity === 2 &&
        config.enable_segmentation &&
        config.smooth_segmentation
    ) return "posthoc";
    return "custom";
}

/** Shared slider sx that matches the camera config panel style. */
const useSliderSx = () => {
    const theme = useTheme();
    return {
        color: theme.palette.primary.light,
        "& .MuiSlider-thumb": {
            "&:hover, &.Mui-focusVisible": {
                boxShadow: `0px 0px 0px 8px ${theme.palette.primary.light}33`,
            },
        },
    } as const;
};

export const MediapipeConfigPanel: React.FC = () => {
    const theme = useTheme();
    const sliderSx = useSliderSx();
    const {detectorConfig, updateDetectorConfig, replaceDetectorConfig, isLoading} = useMocap();

    const currentPreset = detectPreset(detectorConfig);

    const handlePresetChange = useCallback(
        (preset: DetectorPreset) => {
            if (preset === "realtime") replaceDetectorConfig({...MEDIAPIPE_REALTIME_PRESET});
            else if (preset === "posthoc") replaceDetectorConfig({...MEDIAPIPE_POSTHOC_PRESET});
        },
        [replaceDetectorConfig]
    );

    return (
        <Stack spacing={2}>
            <Typography variant="subtitle2" sx={{color: theme.palette.text.secondary, fontWeight: 600}}>
                MediaPipe Detector
            </Typography>

            {/* Preset selector */}
            <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="caption" sx={{color: theme.palette.text.secondary, minWidth: 48}}>
                    Preset
                </Typography>
                <Chip
                    label="Realtime"
                    size="small"
                    variant={currentPreset === "realtime" ? "filled" : "outlined"}
                    color={currentPreset === "realtime" ? "primary" : "default"}
                    onClick={() => handlePresetChange("realtime")}
                    disabled={isLoading}
                    sx={{cursor: "pointer"}}
                />
                <Chip
                    label="Posthoc"
                    size="small"
                    variant={currentPreset === "posthoc" ? "filled" : "outlined"}
                    color={currentPreset === "posthoc" ? "primary" : "default"}
                    onClick={() => handlePresetChange("posthoc")}
                    disabled={isLoading}
                    sx={{cursor: "pointer"}}
                />
                {currentPreset === "custom" && (
                    <Chip label="Custom" size="small" variant="outlined" color="warning" />
                )}
            </Stack>

            {/* Model complexity */}
            <FormControl size="small" fullWidth>
                <InputLabel id="model-complexity-label">Model Complexity</InputLabel>
                <Select
                    labelId="model-complexity-label"
                    value={detectorConfig.model_complexity}
                    label="Model Complexity"
                    onChange={(e) =>
                        updateDetectorConfig({
                            model_complexity: e.target.value as MediapipeModelComplexity,
                        })
                    }
                    disabled={isLoading}
                    sx={{color: theme.palette.text.primary}}
                >
                    <MenuItem value={0}>{MODEL_COMPLEXITY_LABELS[0]}</MenuItem>
                    <MenuItem value={1}>{MODEL_COMPLEXITY_LABELS[1]}</MenuItem>
                    <MenuItem value={2}>{MODEL_COMPLEXITY_LABELS[2]}</MenuItem>
                </Select>
            </FormControl>

            {/* Confidence sliders */}
            <Box>
                <Typography variant="caption" color="text.secondary">
                    Min Detection Confidence: {detectorConfig.min_detection_confidence.toFixed(2)}
                </Typography>
                <Slider
                    value={detectorConfig.min_detection_confidence}
                    onChange={(_ , value) =>
                        updateDetectorConfig({min_detection_confidence: value as number})
                    }
                    min={0} max={1} step={0.05} size="small" disabled={isLoading}
                    sx={sliderSx}
                />
            </Box>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Min Tracking Confidence: {detectorConfig.min_tracking_confidence.toFixed(2)}
                </Typography>
                <Slider
                    value={detectorConfig.min_tracking_confidence}
                    onChange={(_, value) =>
                        updateDetectorConfig({min_tracking_confidence: value as number})
                    }
                    min={0} max={1} step={0.05} size="small" disabled={isLoading}
                    sx={sliderSx}
                />
            </Box>

            {/* Boolean toggles */}
            <Stack spacing={0}>
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.smooth_landmarks}
                            onChange={(_, checked) =>
                                updateDetectorConfig({smooth_landmarks: checked})
                            }
                            disabled={isLoading}
                        />
                    }
                    label={<Typography variant="body2">Smooth Landmarks</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.enable_segmentation}
                            onChange={(_, checked) =>
                                updateDetectorConfig({enable_segmentation: checked})
                            }
                            disabled={isLoading}
                        />
                    }
                    label={<Typography variant="body2">Enable Segmentation</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.smooth_segmentation}
                            onChange={(_, checked) =>
                                updateDetectorConfig({smooth_segmentation: checked})
                            }
                            disabled={isLoading || !detectorConfig.enable_segmentation}
                        />
                    }
                    label={<Typography variant="body2">Smooth Segmentation</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.refine_face_landmarks}
                            onChange={(_, checked) =>
                                updateDetectorConfig({refine_face_landmarks: checked})
                            }
                            disabled={isLoading}
                        />
                    }
                    label={<Typography variant="body2">Refine Face Landmarks</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.static_image_mode}
                            onChange={(_, checked) =>
                                updateDetectorConfig({static_image_mode: checked})
                            }
                            disabled={isLoading}
                        />
                    }
                    label={<Typography variant="body2">Static Image Mode</Typography>}
                />
            </Stack>
        </Stack>
    );
};
