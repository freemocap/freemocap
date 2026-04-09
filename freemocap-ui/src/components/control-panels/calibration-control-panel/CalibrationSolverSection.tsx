import React from "react";
import {
    FormControl,
    FormControlLabel,
    InputLabel,
    MenuItem,
    Select,
    Stack,
    Switch,
    Typography,
    useTheme,
} from "@mui/material";
import {useCalibration} from "@/hooks/useCalibration";
import {CalibrationSolverMethod} from "@/store/slices/calibration";

/**
 * Calibration solver method and groundplane controls.
 *
 * Drop this into CalibrationControlPanel's Stack, after the
 * square length TextField and before the recording progress section.
 */
export const CalibrationSolverSection: React.FC = () => {
    const theme = useTheme();
    const {config, updateCalibrationConfig, isLoading} = useCalibration();

    return (
        <Stack spacing={2}>
            <Typography
                variant="subtitle2"
                sx={{color: theme.palette.text.secondary, fontWeight: 600}}
            >
                Solver Settings
            </Typography>

            {/* Solver Method */}
            <FormControl size="small" fullWidth>
                <InputLabel id="solver-method-label">Solver Method</InputLabel>
                <Select
                    labelId="solver-method-label"
                    value={config.solverMethod}
                    label="Solver Method"
                    onChange={(e) =>
                        updateCalibrationConfig({
                            solverMethod: e.target.value as CalibrationSolverMethod,
                        })
                    }
                    disabled={isLoading}
                    sx={{color: theme.palette.text.primary}}
                >
                    <MenuItem value="anipose">Anipose (legacy)</MenuItem>
                    <MenuItem value="pyceres">Pyceres (bundle adjustment)</MenuItem>
                </Select>
            </FormControl>

            {/* Groundplane */}
            <FormControlLabel
                control={
                    <Switch
                        size="small"
                        checked={config.useGroundplane}
                        onChange={(_, checked) =>
                            updateCalibrationConfig({useGroundplane: checked})
                        }
                        disabled={isLoading}
                    />
                }
                label={
                    <Typography variant="body2">
                        Align to ground plane
                    </Typography>
                }
            />
        </Stack>
    );
};
