// CameraConfigRotation.tsx
import * as React from 'react';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import {Box, Tooltip, useTheme} from '@mui/material';
import {RotationOptions, RotationLabels} from "@/store/slices/cameras-slices/camera-types";
import {z} from 'zod';

interface CameraConfigRotationProps {
    rotation?: number; // Use number directly
    onChange: (rotation: number) => void;
}

export const CameraConfigRotation: React.FC<CameraConfigRotationProps> = ({
    rotation = -1, // Set default value to -1 for NO_ROTATION
    onChange
}) => {
    const theme = useTheme();
    const handleChange = (
        event: React.MouseEvent<HTMLElement>,
        newRotation: number,
    ) => {
        if (newRotation !== null) {
            onChange(newRotation);
        }
    };

    return (
        <Box>
            <Tooltip title="Select camera image rotation">
                <ToggleButtonGroup
                    color={theme.palette.primary.main as any}
                    value={rotation}
                    size="small"
                    exclusive
                    onChange={handleChange}
                    aria-label="camera rotation"
                    sx={{
                        '& .MuiToggleButton-root.Mui-selected': {
                            backgroundColor: theme.palette.primary.main,
                            color: theme.palette.primary.contrastText,
                            border: `1px solid ${theme.palette.text.secondary}`,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.light,
                            },
                        }
                    }}
                >
                    {/* Map through RotationOptions and RotationLabels to create buttons */}
                    {RotationOptions.map((value, index) => (
                        <ToggleButton key={value} value={value}>
                            {RotationLabels[index]}
                        </ToggleButton>
                    ))}
                </ToggleButtonGroup>
            </Tooltip>
        </Box>
    );
}