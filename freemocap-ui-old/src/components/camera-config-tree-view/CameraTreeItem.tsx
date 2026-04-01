import React from "react";
import {Box, Chip, IconButton, Typography, useTheme} from "@mui/material";
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import VideocamIcon from "@mui/icons-material/Videocam";
import SettingsIcon from "@mui/icons-material/Settings";

import {CameraConfigTreeSection} from "./CameraConfigTreeSection";
import {ROTATION_DEGREE_LABELS, RotationValue, useAppDispatch} from "@/store";
import {cameraSelectionToggled} from "@/store/slices/cameras/cameras-slice";
import {Camera} from "@/store/slices/cameras/cameras-types";

interface CameraTreeItemProps {
    camera: Camera;
    isExpanded?: boolean;
}

// Helper function to format config summary
const getConfigSummary = (config: any): string[] => {
    const summary: string[] = [];

    if (!config) return summary;

    // Add resolution if available
    if (config.resolution?.width && config.resolution?.height) {
        summary.push(`${config.resolution.width}×${config.resolution.height}`);
    }

    if (config.framerate) {
        summary.push(`${parseFloat(config.framerate).toFixed(2)}fps`);
    }

    // Add exposure if available and not AUTO
    if (config.exposure !== undefined && config.exposure_mode === 'MANUAL') {
        summary.push(`E:${config.exposure}`);
    }

    // Add pixel format if available and not default
    if (config.pixel_format && config.pixel_format !== 'RGB') {
        summary.push(config.pixel_format);
    }

    if (config.rotation) {
        summary.push(ROTATION_DEGREE_LABELS[config.rotation as RotationValue]);
    }
    // Add capture format if different from default
    if (config.capture_fourcc) {
        summary.push(config.capture_fourcc);
    }

    return summary.filter(item => item); // Remove empty strings
};

export const CameraTreeItem: React.FC<CameraTreeItemProps> = ({camera, isExpanded = false}) => {
    const dispatch = useAppDispatch();
    const theme = useTheme();

    const handleToggleSelection = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(cameraSelectionToggled(camera.id));
    };

    const getStatusColor = (): string => {
        switch (camera.connectionStatus) {
            case "connected":
                return theme.palette.success.main;
            case "available":
                return theme.palette.info.main;
            case "error":
                return theme.palette.error.main;
            default:
                return theme.palette.grey[500];
        }
    };

    const configSummary = getConfigSummary(camera.desiredConfig);
    const showConfigSummary = !isExpanded && configSummary.length > 0;

    return (
        <TreeItem
            itemId={`camera-${camera.id}`}
            label={
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        py: 0.2,
                        pr: 1,
                        minHeight: 32,
                    }}
                >
                    {/* Selection checkbox */}
                    <IconButton
                        size="small"
                        onClick={handleToggleSelection}
                        sx={{mr: 1, flexShrink: 0}}
                    >
                        {camera.selected ? (
                            <CheckCircleIcon color="info"/>
                        ) : (
                            <RadioButtonUncheckedIcon color="info"/>
                        )}
                    </IconButton>

                    {/* Camera icon */}
                    <VideocamIcon sx={{mr: 1, color: getStatusColor(), flexShrink: 0}}/>

                    {/* Camera name and config summary container */}
                    <Box sx={{
                        display: "flex",
                        alignItems: "center",
                        flexGrow: 1,
                        minWidth: 0, // Allow shrinking
                        gap: 1
                    }}>
                        {/* Camera name */}
                        <Typography
                            variant="body2"
                            sx={{
                                flexShrink: 0,
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                maxWidth: "200px" // Limit name width
                            }}
                        >
                            <span style={{fontSize: '0.75rem'}}>

                            Camera {camera.index}
                            </span>
                            <br/>
                            <span style={{fontSize: '0.6rem'}}>
                                {camera.name} (id: {camera.id})
                            </span>
                        </Typography>

                        {/* Config summary - only show when collapsed */}
                        {showConfigSummary && (
                            <Box sx={{
                                display: "flex",
                                alignItems: "center",
                                gap: 0.25,
                                flexGrow: 1,
                                minWidth: 0,
                                overflow: "hidden"
                            }}>
                                <SettingsIcon
                                    sx={{
                                        fontSize: 14,
                                        color: theme.palette.text.secondary,
                                        flexShrink: 0
                                    }}
                                />
                                <Box sx={{
                                    display: "flex",
                                    gap: 0.5,
                                    flexWrap: "wrap",
                                    overflow: "hidden"
                                }}>
                                    {configSummary.slice(0, 5).map((item, index) => (
                                        <Chip
                                            key={index}
                                            label={item}
                                            size="small"
                                            variant="outlined"
                                            sx={{
                                                height: 10,
                                                fontSize: 8,
                                                '& .MuiChip-label': {
                                                    px: 0.75,
                                                },
                                                borderColor: theme.palette.divider,
                                                color: theme.palette.text.secondary,
                                            }}
                                        />
                                    ))}
                                </Box>
                            </Box>
                        )}
                    </Box>

                    {/* Status chip */}
                    <Chip
                        label={camera.connectionStatus.toUpperCase()}
                        size="small"
                        sx={{
                            ml: 1,
                            flexShrink: 0,
                            backgroundColor: getStatusColor(),
                            color: theme.palette.getContrastText(getStatusColor()),
                            fontSize: 10,
                            height: 20,
                        }}
                    />
                </Box>
            }
        >
            <CameraConfigTreeSection camera={camera}/>
        </TreeItem>
    );
};
