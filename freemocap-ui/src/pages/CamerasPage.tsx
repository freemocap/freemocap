import React, {useState, useCallback} from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Footer} from "@/components/ui-components/Footer";
import {useTheme} from "@mui/material/styles";
import {CameraViewsGrid} from "@/components/camera-views/CameraViewsGrid";
import {CamerasViewSettingsOverlay} from "@/components/camera-view-settings-overlay/CamerasViewSettingsOverlay";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";

export type LayoutDirection = 'vertical' | 'horizontal';

export interface CameraSettings {
    columns: number | null;
    show3dView: boolean;
    layoutDirection: LayoutDirection;
}

export const CamerasPage = () => {
    const theme = useTheme();
    const [resetKey, setResetKey] = useState<number>(0);
    const [settings, setSettings] = useState<CameraSettings>({
        columns: null,
        show3dView: true,
        layoutDirection: 'horizontal',
    });

    const handleSettingsChange = useCallback((partial: Partial<CameraSettings>) => {
        setSettings((prev) => ({...prev, ...partial}));
    }, []);

    const handleResetLayout = useCallback(() => {
        setResetKey((v) => v + 1);
    }, []);

    const isHorizontal = settings.layoutDirection === 'horizontal';

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
                    settings={settings}
                    onSettingsChange={handleSettingsChange}
                    onResetLayout={handleResetLayout}
                />

                <Box sx={{flex: 1, overflow: 'hidden'}}>
                    {settings.show3dView ? (
                        <PanelGroup
                            key={`main-panels-${resetKey}-${settings.layoutDirection}`}
                            direction={settings.layoutDirection}
                        >
                            {/* Camera Grid View Panel */}
                            <Panel defaultSize={75} minSize={20}>
                                <Box sx={{height: '100%', overflow: 'auto'}}>
                                    <ErrorBoundary>
                                        <CameraViewsGrid manualColumns={settings.columns} resetKey={resetKey}/>
                                    </ErrorBoundary>
                                </Box>
                            </Panel>

                            {/* Resize Handle — direction-aware sizing and drag indicator */}
                            <PanelResizeHandle>
                                <Box
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        backgroundColor: theme.palette.divider,
                                        transition: 'background-color 0.15s ease',
                                        cursor: isHorizontal ? 'col-resize' : 'row-resize',
                                        ...(isHorizontal
                                            ? {width: '6px', height: '100%', flexDirection: 'column'}
                                            : {height: '6px', width: '100%', flexDirection: 'row'}
                                        ),
                                        '&:hover': {
                                            backgroundColor: theme.palette.primary.main,
                                        },
                                        '&:active': {
                                            backgroundColor: theme.palette.primary.dark,
                                        },
                                    }}
                                >
                                    {/* Drag grip dots */}
                                    {[0, 1, 2].map((i) => (
                                        <Box
                                            key={i}
                                            sx={{
                                                width: isHorizontal ? 4 : 4,
                                                height: isHorizontal ? 4 : 4,
                                                borderRadius: '50%',
                                                backgroundColor: theme.palette.text.disabled,
                                                m: isHorizontal ? '2px 0' : '0 2px',
                                                flexShrink: 0,
                                            }}
                                        />
                                    ))}
                                </Box>
                            </PanelResizeHandle>

                            {/* 3D View Panel */}
                            <Panel defaultSize={25} minSize={10}>
                                <Box sx={{height: '100%'}}>
                                    <ThreeJsCanvas/>
                                </Box>
                            </Panel>
                        </PanelGroup>
                    ) : (
                        <Box sx={{height: '100%', overflow: 'auto'}}>
                            <ErrorBoundary>
                                <CameraViewsGrid manualColumns={settings.columns} resetKey={resetKey}/>
                            </ErrorBoundary>
                        </Box>
                    )}
                </Box>

                <Box component="footer" sx={{p: 1, flexShrink: 0}}>
                    <Footer/>
                </Box>
            </Box>
        </React.Fragment>
    );
};
