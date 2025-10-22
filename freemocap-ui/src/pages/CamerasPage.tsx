import React, { useState } from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import { Footer } from "@/components/ui-components/Footer";
import { useTheme } from "@mui/material/styles";
import { CameraViewsGrid } from "@/components/camera-views/CameraViewsGrid";
import {CamerasViewSettingsOverlay} from "@/components/camera-view-settings-overlay/CamerasViewSettingsOverlay";

interface CameraSettings {
    columns: number | null;
}

export const CamerasPage = () => {
    const theme = useTheme();
    const [settings, setSettings] = useState<CameraSettings>({
        columns: null, // auto
    });

    const handleSettingsChange = (newSettings: CameraSettings) => {
        setSettings(newSettings);
    };

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
                overflow: "scroll",
                position: 'relative', // For absolute positioning of overlay
            }}>
                <CamerasViewSettingsOverlay onSettingsChange={handleSettingsChange} />

                <Box>
                    <ErrorBoundary>
                        <CameraViewsGrid settings={settings} />
                    </ErrorBoundary>
                </Box>
                <Box component="footer" sx={{ p: 1 }}>
                    <Footer />
                </Box>
            </Box>
        </React.Fragment>
    );
};
