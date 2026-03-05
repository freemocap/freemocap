import React, {useCallback} from "react";
import {
    Box,
    Button,
    Divider,
    Slider,
    Stack,
    TextField,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import {useMocap} from "@/hooks/useMocap";
import {DEFAULT_REALTIME_FILTER_CONFIG} from "@/store/slices/mocap";

/** Warm amber for section headings — visible on dark backgrounds. */
const SECTION_COLOR = "#ffb74d";

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

export const SkeletonFilterConfigPanel: React.FC = () => {
    const theme = useTheme();
    const sliderSx = useSliderSx();
    const {skeletonFilterConfig, updateSkeletonFilterConfig, replaceSkeletonFilterConfig, isLoading} = useMocap();

    const handleResetDefaults = useCallback(() => {
        replaceSkeletonFilterConfig({...DEFAULT_REALTIME_FILTER_CONFIG});
    }, [replaceSkeletonFilterConfig]);

    return (
        <Stack spacing={1}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle2" sx={{color: theme.palette.text.secondary, fontWeight: 600}}>
                    Skeleton Filter
                </Typography>
                <Button
                    size="small"
                    variant="text"
                    onClick={handleResetDefaults}
                    disabled={isLoading}
                    sx={{fontSize: 11, textTransform: "none"}}
                >
                    Reset Defaults
                </Button>
            </Stack>

            {/* === Point Gate === */}
            <Typography variant="caption" sx={{color: SECTION_COLOR, fontWeight: 600}}>
                Point Gate
            </Typography>

            <Tooltip title="Reject triangulated points whose mean reprojection error exceeds this. Higher = keep more (noisier) points." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        Max Reproj Error: {skeletonFilterConfig.max_reprojection_error_px.toFixed(0)} px
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.max_reprojection_error_px}
                        onChange={(_, v) => updateSkeletonFilterConfig({max_reprojection_error_px: v as number})}
                        min={5} max={200} step={1} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>

            <Tooltip title="Reject points moving faster than this between frames. Catches teleportation spikes. Human limbs rarely exceed ~15 m/s." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        Max Velocity: {skeletonFilterConfig.max_velocity_m_per_s.toFixed(0)} m/s
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.max_velocity_m_per_s}
                        onChange={(_, v) => updateSkeletonFilterConfig({max_velocity_m_per_s: v as number})}
                        min={5} max={200} step={1} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>

            <Tooltip title="After this many consecutive velocity rejections, accept unconditionally to prevent permanent lockout." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        Max Rejected Streak: {skeletonFilterConfig.max_rejected_streak}
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.max_rejected_streak}
                        onChange={(_, v) => updateSkeletonFilterConfig({max_rejected_streak: v as number})}
                        min={1} max={30} step={1} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>

            <Divider />

            {/* === One Euro Filter === */}
            <Typography variant="caption" sx={{color: SECTION_COLOR, fontWeight: 600}}>
                One Euro Filter
            </Typography>

            <Tooltip title="Minimum cutoff frequency (Hz). Lower = heavier smoothing (less jitter, more lag). Higher = more responsive." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        Min Cutoff: {skeletonFilterConfig.min_cutoff.toFixed(4)}
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.min_cutoff}
                        onChange={(_, v) => updateSkeletonFilterConfig({min_cutoff: v as number})}
                        min={0.0001} max={0.1} step={0.0005} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>

            <Tooltip title="Speed coefficient. Higher = less lag during fast motion but more jitter. Zero = constant smoothing regardless of speed." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        Beta: {skeletonFilterConfig.beta.toFixed(2)}
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.beta}
                        onChange={(_, v) => updateSkeletonFilterConfig({beta: v as number})}
                        min={0} max={5} step={0.05} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>

            <Tooltip title="Cutoff frequency for the speed estimator. Controls how quickly the filter reacts to speed changes. Usually fine at 1.0." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        D Cutoff: {skeletonFilterConfig.d_cutoff.toFixed(2)}
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.d_cutoff}
                        onChange={(_, v) => updateSkeletonFilterConfig({d_cutoff: v as number})}
                        min={0.1} max={5} step={0.1} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>

            <Divider />

            {/* === FABRIK === */}
            <Typography variant="caption" sx={{color: SECTION_COLOR, fontWeight: 600}}>
                FABRIK
            </Typography>

            <Tooltip title="Max solver iterations per frame for bone length constraint enforcement. 10–30 is usually plenty." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        Max Iterations: {skeletonFilterConfig.fabrik_max_iterations}
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.fabrik_max_iterations}
                        onChange={(_, v) => updateSkeletonFilterConfig({fabrik_max_iterations: v as number})}
                        min={1} max={100} step={1} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>

            <Divider />

            {/* === Body Model === */}
            <Typography variant="caption" sx={{color: SECTION_COLOR, fontWeight: 600}}>
                Body Model
            </Typography>

            <Tooltip title="Subject's approximate height. Scales the anthropometric bone length prior. Doesn't need to be exact." placement="right" arrow>
                <TextField
                    label="Height (m)"
                    type="number"
                    size="small"
                    value={skeletonFilterConfig.height_meters}
                    onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        if (!isNaN(val) && val > 0) {
                            updateSkeletonFilterConfig({height_meters: val});
                        }
                    }}
                    inputProps={{step: 0.01, min: 0.5, max: 3.0}}
                    disabled={isLoading}
                    fullWidth
                />
            </Tooltip>

            <Tooltip title="Expected measurement noise (meters). Higher = trust raw positions less, rely more on prior estimates." placement="right" arrow>
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        Noise Sigma: {skeletonFilterConfig.noise_sigma.toFixed(4)} m
                    </Typography>
                    <Slider
                        value={skeletonFilterConfig.noise_sigma}
                        onChange={(_, v) => updateSkeletonFilterConfig({noise_sigma: v as number})}
                        min={0.001} max={0.05} step={0.001} size="small" disabled={isLoading}
                        sx={sliderSx}
                    />
                </Box>
            </Tooltip>
        </Stack>
    );
};
