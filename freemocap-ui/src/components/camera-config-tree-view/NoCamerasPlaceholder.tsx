import React from "react";
import { Box, Typography } from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";

export const NoCamerasPlaceholder: React.FC = () => {
    return (
        <TreeItem
            itemId="no-cameras"
            label={
                <Box
                    sx={{
                        p: 3,
                        textAlign: "center",
                        bgcolor: "background.paper",
                    }}
                >
                    <Typography variant="body1" color="text.secondary">
                        No cameras detected
                    </Typography>
                    <Typography
                        variant="caption"
                        color="text.disabled"
                        sx={{ mt: 1, display: "block" }}
                    >
                        Click refresh to scan for available cameras
                    </Typography>
                </Box>
            }
        />
    );
};
