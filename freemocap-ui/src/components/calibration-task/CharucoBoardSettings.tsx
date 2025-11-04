// components/CharucoBoardSettings.tsx
import React from 'react';
import {
    TextField,
    Stack,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    SelectChangeEvent,
} from '@mui/material';
import {BoardType, CalibrationConfig, getBoardSizeForType} from "@/store";

interface CharucoBoardSettingsProps {
    config: CalibrationConfig;
    disabled: boolean;
    onConfigUpdate: (updates: Partial<CalibrationConfig>) => void;
}

export const CharucoBoardSettings: React.FC<CharucoBoardSettingsProps> = ({
                                                                              config,
                                                                              disabled,
                                                                              onConfigUpdate,
                                                                          }) => {
    const handleBoardTypeChange = (event: SelectChangeEvent<BoardType>): void => {
        const boardType = event.target.value as BoardType;
        const updates: Partial<CalibrationConfig> = { boardType };

        if (boardType !== 'custom') {
            updates.boardSize = getBoardSizeForType(boardType);
        }

        onConfigUpdate(updates);
    };

    const handleNumberChange = (value: string, min: number = 1): number | null => {
        const num = parseInt(value, 10);
        return isNaN(num) || num < min ? null : num;
    };

    return (
        <Stack spacing={2}>
            {/* Board Type */}
            <FormControl fullWidth size="small">
                <InputLabel>Board Type</InputLabel>
                <Select
                    value={config.boardType}
                    label="Board Type"
                    onChange={handleBoardTypeChange}
                    disabled={disabled}
                >
                    <MenuItem value="5x3">5x3 Board</MenuItem>
                    <MenuItem value="7x5">7x5 Board</MenuItem>
                    <MenuItem value="custom">Custom</MenuItem>
                </Select>
            </FormControl>

            {/* Custom Board Size */}
            {config.boardType === 'custom' && (
                <Stack direction="row" spacing={2}>
                    <TextField
                        label="Rows"
                        type="number"
                        size="small"
                        value={config.boardSize.rows}
                        onChange={(e) => {
                            const rows = handleNumberChange(e.target.value);
                            if (rows !== null) {
                                onConfigUpdate({ boardSize: { ...config.boardSize, rows } });
                            }
                        }}
                        disabled={disabled}
                        inputProps={{ min: 1 }}
                        fullWidth
                    />
                    <TextField
                        label="Columns"
                        type="number"
                        size="small"
                        value={config.boardSize.cols}
                        onChange={(e) => {
                            const cols = handleNumberChange(e.target.value);
                            if (cols !== null) {
                                onConfigUpdate({ boardSize: { ...config.boardSize, cols } });
                            }
                        }}
                        disabled={disabled}
                        inputProps={{ min: 1 }}
                        fullWidth
                    />
                </Stack>
            )}

            {/* Square Size */}
            <TextField
                label="Square Size (mm)"
                type="number"
                size="small"
                value={config.squareSize}
                onChange={(e) => {
                    const squareSize = handleNumberChange(e.target.value);
                    if (squareSize !== null) {
                        onConfigUpdate({ squareSize });
                    }
                }}
                disabled={disabled}
                inputProps={{ min: 1 }}
                fullWidth
            />

            {/* Min Shared Views */}
            <TextField
                label="Min Shared Views per Camera"
                type="number"
                size="small"
                value={config.minSharedViews}
                onChange={(e) => {
                    const minSharedViews = handleNumberChange(e.target.value);
                    if (minSharedViews !== null) {
                        onConfigUpdate({ minSharedViews });
                    }
                }}
                disabled={disabled}
                inputProps={{ min: 1 }}
                fullWidth
            />
        </Stack>
    );
};
