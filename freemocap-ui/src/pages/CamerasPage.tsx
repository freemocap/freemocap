import React, { useState } from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import { Footer } from "@/components/ui-components/Footer";
import { useTheme } from "@mui/material/styles";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { CameraViewsGrid } from "@/components/camera-views/CameraViewsGrid";
import { CamerasViewSettingsOverlay } from "@/components/camera-view-settings-overlay/CamerasViewSettingsOverlay";
import { ThreeJsCanvas } from "@/components/viewport3d/ThreeJsCanvas";

interface CameraSettings {
    columns: number | null;
    show3dView: boolean;
}

export const CamerasPage = () => {
    const theme = useTheme();
    const [settings, setSettings] = useState<CameraSettings>({
        columns: null, // auto
        show3dView: true,
    });
    const [resetKey, setResetKey] = useState<number>(0);

    const handleSettingsChange = (newSettings: CameraSettings) => {
        setSettings(newSettings);
    };

    const handleResetViews = () => {
        setResetKey(prev => prev + 1);
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
                overflow: "hidden",
                position: 'relative',
            }}>
                <CamerasViewSettingsOverlay
                    onSettingsChange={handleSettingsChange}
                    onResetViews={handleResetViews}
                />

                <Box sx={{ flex: 1, overflow: 'hidden' }}>
                    {settings.show3dView ? (
                        <PanelGroup key={`main-panels-${resetKey}`} direction="vertical">
                            {/* Camera Grid View Panel */}
                            <Panel defaultSize={80} minSize={20}>
                                <Box sx={{ height: '100%', overflow: 'auto' }}>
                                    <ErrorBoundary>
                                        <CameraViewsGrid settings={settings} resetKey={resetKey} />
                                    </ErrorBoundary>
                                </Box>
                            </Panel>

                            {/* Vertical Resize Handle */}
                            <PanelResizeHandle
                                style={{
                                    height: "2px",
                                    cursor: "row-resize",
                                    backgroundColor: theme.palette.primary.dark,
                                }}
                            />

                            {/* 3D View Panel */}
                            <Panel defaultSize={20} minSize={10}>
                                <Box sx={{ height: '100%' }}>
                                    <ThreeJsCanvas />
                                </Box>
                            </Panel>
                        </PanelGroup>
                    ) : (
                        <Box sx={{ height: '100%', overflow: 'auto' }}>
                            <ErrorBoundary>
                                <CameraViewsGrid settings={settings} resetKey={resetKey} />
                            </ErrorBoundary>
                        </Box>
                    )}
                </Box>

                <Box component="footer" sx={{ p: 1 }}>
                    <Footer />
                </Box>
            </Box>
        </React.Fragment>
    );
};
