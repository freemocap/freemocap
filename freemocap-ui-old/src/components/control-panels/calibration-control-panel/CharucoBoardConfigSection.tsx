import React, {useCallback, useMemo} from "react";
import {
    Stack,
    TextField,
    Typography,
    useTheme,
} from "@mui/material";
import {useCalibration} from "@/hooks/useCalibration";
import {PresetPicker} from "@/components/common/PresetPicker";

type BoardPreset = "5x3" | "7x5" | "custom";

interface BoardPresetConfig {
    squares_x: number;
    squares_y: number;
}

const BOARD_PRESETS: Record<Exclude<BoardPreset, "custom">, BoardPresetConfig> = {
    "5x3": {squares_x: 5, squares_y: 3},
    "7x5": {squares_x: 7, squares_y: 5},
};

export const CharucoBoardConfigSection: React.FC = () => {
    const theme = useTheme();
    const {config, updateCalibrationConfig, isLoading} = useCalibration();
    const board = config.charucoBoard;

    const currentPreset = useMemo<BoardPreset>(() => {
        for (const [preset, presetConfig] of Object.entries(BOARD_PRESETS)) {
            if (presetConfig.squares_x === board.squares_x && presetConfig.squares_y === board.squares_y) {
                return preset as BoardPreset;
            }
        }
        return "custom";
    }, [board.squares_x, board.squares_y]);

    const handlePresetChange = useCallback(
        (preset: BoardPreset): void => {
            if (preset === "custom") return;
            const presetConfig = BOARD_PRESETS[preset];
            updateCalibrationConfig({
                charucoBoard: {...board, ...presetConfig},
            });
        },
        [board, updateCalibrationConfig],
    );

    return (
        <Stack spacing={2} sx={{p:2}}>
            <Typography variant="subtitle2" sx={{color: theme.palette.text.secondary, fontWeight: 600}}>
                Charuco Board
            </Typography>

            {/* Preset */}
            <PresetPicker
                label="Preset"
                value={currentPreset}
                options={[
                    {value: "5x3" as BoardPreset, label: "5×3"},
                    {value: "7x5" as BoardPreset, label: "7×5"},
                    {value: "custom" as BoardPreset, label: "Custom"},
                ]}
                onChange={handlePresetChange}
                disabled={isLoading}
                minWidth={140}
            />

            {/* X / Y Squares */}
            <Stack direction="row" spacing={2}>
                <TextField
                    label="X Squares"
                    type="number"
                    value={board.squares_x}
                    onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (!isNaN(v) && v > 0) updateCalibrationConfig({charucoBoard: {...board, squares_x: v}});
                    }}
                    disabled={isLoading}
                    size="small"
                    sx={{flex: 1}}
                    inputProps={{min: 2, max: 20}}
                />
                <TextField
                    label="Y Squares"
                    type="number"
                    value={board.squares_y}
                    onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (!isNaN(v) && v > 0) updateCalibrationConfig({charucoBoard: {...board, squares_y: v}});
                    }}
                    disabled={isLoading}
                    size="small"
                    sx={{flex: 1}}
                    inputProps={{min: 2, max: 20}}
                />
            </Stack>

            {/* Square Length */}
            <TextField
                label="Square Length (mm)"
                type="number"
                value={board.square_length_mm}
                onChange={(e) => {
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v) && v > 0) updateCalibrationConfig({charucoBoard: {...board, square_length_mm: v}});
                }}
                disabled={isLoading}
                size="small"
                fullWidth
                inputProps={{min: 1, step: 0.1}}
            />
        </Stack>
    );
};
