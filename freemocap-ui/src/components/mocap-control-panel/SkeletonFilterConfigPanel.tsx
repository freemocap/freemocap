import React, {useCallback} from "react";
import {
    Box,
    Button,
    Divider,
    Slider,
    Stack,
    TextField,
    Typography,
    useTheme,
} from "@mui/material";
import {useMocap} from "@/hooks/useMocap";
import {DEFAULT_REALTIME_FILTER_CONFIG} from "@/store/slices/mocap";

export const SkeletonFilterConfigPanel: React.FC = () => {
    const theme = useTheme();
    const {skeletonFilterConfig, updateSkeletonFilterConfig, replaceSkeletonFilterConfig, isLoading} = useMocap();

    const handleResetDefaults = useCallback(() => {
        replaceSkeletonFilterConfig({...DEFAULT_REALTIME_FILTER_CONFIG});
    }, [replaceSkeletonFilterConfig]);

    return (
        <Stack spacing={2}>
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

            {/* === Point Gate Section === */}
            <Typography variant="caption" sx={{color: theme.palette.info.main, fontWeight: 600}}>
                Point Gate (reject bad triangulations)
            </Typography>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Max Reprojection Error: {skeletonFilterConfig.max_reprojection_error_px.toFixed(1)} px
                </Typography>
                <Slider
                    value={skeletonFilterConfig.max_reprojection_error_px}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({max_reprojection_error_px: value as number})
                    }
                    min={1}
                    max={100}
                    step={1}
                    size="small"
                    disabled={isLoading}
                />
            </Box>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Max Velocity: {skeletonFilterConfig.max_velocity_m_per_s.toFixed(1)} m/s
                </Typography>
                <Slider
                    value={skeletonFilterConfig.max_velocity_m_per_s}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({max_velocity_m_per_s: value as number})
                    }
                    min={1}
                    max={100}
                    step={1}
                    size="small"
                    disabled={isLoading}
                />
            </Box>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Max Rejected Streak: {skeletonFilterConfig.max_rejected_streak}
                </Typography>
                <Slider
                    value={skeletonFilterConfig.max_rejected_streak}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({max_rejected_streak: value as number})
                    }
                    min={1}
                    max={60}
                    step={1}
                    size="small"
                    disabled={isLoading}
                />
            </Box>

            <Divider sx={{my: 0.5}} />

            {/* === One Euro Filter Section === */}
            <Typography variant="caption" sx={{color: theme.palette.info.main, fontWeight: 600}}>
                One Euro Filter (smoothing)
            </Typography>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Min Cutoff: {skeletonFilterConfig.min_cutoff.toFixed(4)}
                </Typography>
                <Slider
                    value={skeletonFilterConfig.min_cutoff}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({min_cutoff: value as number})
                    }
                    min={0.0001}
                    max={0.1}
                    step={0.0005}
                    size="small"
                    disabled={isLoading}
                />
            </Box>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Beta (speed coefficient): {skeletonFilterConfig.beta.toFixed(2)}
                </Typography>
                <Slider
                    value={skeletonFilterConfig.beta}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({beta: value as number})
                    }
                    min={0}
                    max={5}
                    step={0.05}
                    size="small"
                    disabled={isLoading}
                />
            </Box>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    D Cutoff: {skeletonFilterConfig.d_cutoff.toFixed(2)}
                </Typography>
                <Slider
                    value={skeletonFilterConfig.d_cutoff}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({d_cutoff: value as number})
                    }
                    min={0.1}
                    max={5}
                    step={0.1}
                    size="small"
                    disabled={isLoading}
                />
            </Box>

            <Divider sx={{my: 0.5}} />

            {/* === FABRIK Section === */}
            <Typography variant="caption" sx={{color: theme.palette.info.main, fontWeight: 600}}>
                FABRIK (bone length constraints)
            </Typography>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Max Iterations: {skeletonFilterConfig.fabrik_max_iterations}
                </Typography>
                <Slider
                    value={skeletonFilterConfig.fabrik_max_iterations}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({fabrik_max_iterations: value as number})
                    }
                    min={1}
                    max={100}
                    step={1}
                    size="small"
                    disabled={isLoading}
                />
            </Box>

            <Divider sx={{my: 0.5}} />

            {/* === Body / Estimation Section === */}
            <Typography variant="caption" sx={{color: theme.palette.info.main, fontWeight: 600}}>
                Body Model
            </Typography>

            <TextField
                label="Height (meters)"
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

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Noise Sigma: {skeletonFilterConfig.noise_sigma.toFixed(4)} m
                </Typography>
                <Slider
                    value={skeletonFilterConfig.noise_sigma}
                    onChange={(_, value) =>
                        updateSkeletonFilterConfig({noise_sigma: value as number})
                    }
                    min={0.001}
                    max={0.05}
                    step={0.001}
                    size="small"
                    disabled={isLoading}
                />
            </Box>
        </Stack>
    );
};
