import React from "react";
import { Box, Typography } from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import { useTranslation } from "react-i18next";

export const NoCamerasPlaceholder: React.FC = () => {
    const { t } = useTranslation();
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
                        {t('noCamerasDetected')}
                    </Typography>
                    <Typography
                        variant="caption"
                        color="text.disabled"
                        sx={{ mt: 1, display: "block" }}
                    >
                        {t('clickRefreshToScan')}
                    </Typography>
                </Box>
            }
        />
    );
};
