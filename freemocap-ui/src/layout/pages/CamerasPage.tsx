// skellycam-ui/src/layout/BaseContent.tsx
import React from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/ErrorBoundary";
import {Copyright} from "@/components/ui-components/Copyright";
import {useTheme} from "@mui/material/styles";
import {CameraImagesGrid} from "@/components/camera-views/og-canvas-strategy/CameraImagesGrid";

export const CamerasPage = () => {
    const theme = useTheme();

    return (
        <React.Fragment>
            <Box sx={{
                py: 1,
                px: 1,
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                width: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                overflow: "scroll"

            }}>
                <Box >
                    <ErrorBoundary>
                        <CameraImagesGrid/>
                    </ErrorBoundary>
                </Box>
                <Box component="footer" sx={{p: 1}}>
                    <Copyright />
                </Box>
            </Box>
        </React.Fragment>
    )
}
