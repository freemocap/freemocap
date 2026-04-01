import React from "react";
import { Box, Typography } from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import { CameraTreeItem } from "./CameraTreeItem";
import { Camera } from "@/store/slices/cameras/cameras-types";

interface CameraGroupTreeItemProps {
    groupId: string;
    title: string;
    cameras: Camera[];
    icon?: React.ReactNode;
    expandedItems?: string[];
}

export const CameraGroupTreeItem: React.FC<CameraGroupTreeItemProps> = ({
                                                                            groupId,
                                                                            title,
                                                                            cameras,
                                                                            icon,
                                                                            expandedItems,
                                                                        }) => {
    return (
        <TreeItem
            itemId={groupId}
            label={
                <Box sx={{ display: "flex", alignItems: "center" }}>
                    {icon}
                    <Typography variant="subtitle2" sx={{ ml: 1 }}>
                        {title} ({cameras.length})
                    </Typography>
                </Box>
            }
        >
            {cameras.map((camera: Camera) => (
                <CameraTreeItem
                    key={camera.id}
                    camera={camera}
                    isExpanded={expandedItems?.includes(`camera-${camera.id}`)}
                />
            ))}
        </TreeItem>
    );
};
