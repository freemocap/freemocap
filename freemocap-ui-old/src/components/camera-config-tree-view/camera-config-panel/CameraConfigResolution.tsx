import React from "react";
import {FormControl, InputLabel, MenuItem, Select, useTheme} from "@mui/material";
import {CameraConfig} from "@/store/slices/cameras/cameras-types";

interface CameraConfigResolutionProps {
    resolution: CameraConfig['resolution'];
    onChange: (width: number, height: number) => void;
}

export const CameraConfigResolution: React.FC<CameraConfigResolutionProps> = ({
                                                                                  resolution,
                                                                                  onChange
                                                                              }) => {
    const theme = useTheme();

    const handleChange = (event: any): void => {
        const [width, height] = event.target.value.split('x').map(Number);
        onChange(width, height);
    };

    return (
        <FormControl size="small" sx={{ flex: 1, color: theme.palette.text.primary }}>
            <InputLabel sx={{ color: theme.palette.text.primary }}>Resolution</InputLabel>
            <Select
                value={`${resolution.width}x${resolution.height}`}
                label="Resolution"
                onChange={handleChange}
                sx={{ color: theme.palette.text.primary }}
            >
                <MenuItem value="640x480">640 x 480</MenuItem>
                <MenuItem value="1280x720">1280 x 720</MenuItem>
                <MenuItem value="1920x1080">1920 x 1080</MenuItem>
            </Select>
        </FormControl>
    );
};
