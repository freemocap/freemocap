// skellycam-ui/src/components/available-cameras-panel/CameraListItem.tsx
import {Box, Checkbox, Chip, IconButton, ListItem, ListItemIcon, ListItemText, Typography, useTheme} from "@mui/material";
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import * as React from "react";
import {CameraDevice} from "@/store/slices/cameras-slices/camera-types";

interface CameraListItemProps {
    camera: CameraDevice;
    isLast: boolean;
    isConfigExpanded: boolean;
    onToggleSelect: () => void;
    onToggleConfig: () => void;
}

export const CameraListItem: React.FC<CameraListItemProps> = ({
    camera,
    isLast,
                                                                  isConfigExpanded,
                                                                  onToggleSelect,
                                                                  onToggleConfig
                                                              }) => {
    const theme = useTheme();

    const getStatusChipProps = (status: string) => {
        switch (status) {
            case 'CONNECTED':
                return { color: 'success' as const, label: 'Connected' };
            case 'AVAILABLE':
                return { color: 'primary' as const, label: 'Available' };
            case 'UNAVAILABLE':
                return { color: 'warning' as const, label: 'Unavailable' };
            case 'IN_USE':
                return { color: 'secondary' as const, label: 'In Use' };
            case 'ERROR':
                return { color: 'error' as const, label: 'Error' };
            default:
                return { color: 'default' as const, label: status || 'Unknown' };
        }
};

    const statusChipProps = getStatusChipProps(camera.status);

    return (
        <ListItem
            sx={{
                '&:hover': {
                    bgcolor: 'action.hover',
                },
                borderBottom: isLast ? 0 : 1,
                borderColor: 'divider',
            }}
        >
            <ListItemIcon>
                <Checkbox
                    edge="start"
                    checked={camera.selected || false}
                    onChange={onToggleSelect}
                    color={theme.palette.primary.main as any}
                    disabled={camera.status === 'UNAVAILABLE' || camera.status === 'ERROR' }
                />
            </ListItemIcon>
            <ListItemText
                primary={
                    <Box sx={{display: 'flex', alignItems: 'center'}}>
                        <Typography
                            component="span"
                            variant="body2"
                            color={theme.palette.text.primary}
                            sx={{mr: 1, fontWeight: 600}}
                        >
                            Camera {camera.index}
                        </Typography>
                        <Typography
                            component="span"
                            variant="body2"
                            color={theme.palette.text.secondary}
                            sx={{mr: 1}}
                        >
                            {`${camera.label}, id: ${camera.cameraId}` || `Unknown Device ${camera.index}`}
                        </Typography>
                        <Chip
                            size="small"
                            label={statusChipProps.label}
                            color={statusChipProps.color}
                            sx={{ ml: 'auto', mr: 1 }}
                        />
                    </Box>
                }
            />
            {camera.selected && camera.status !== 'UNAVAILABLE' && camera.status !== 'ERROR'  && (
                <IconButton
                    size="small"
                    onClick={onToggleConfig}
                >
                    {isConfigExpanded
                        ? <KeyboardArrowUpIcon/>
                        : <KeyboardArrowDownIcon/>}
                </IconButton>
            )}
        </ListItem>
    );
};

