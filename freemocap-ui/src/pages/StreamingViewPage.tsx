import React, {useCallback, useState} from 'react';
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Footer} from "@/components/ui-components/Footer";
import {CameraViewsGrid} from "@/components/camera-views/CameraViewsGrid";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {ThreeJsCanvas} from "@/components/viewport3d/ThreeJsCanvas";
import {SettingsOverlay} from "@/components/ui-components/SettingsOverlay";

export type LayoutDirection = 'vertical' | 'horizontal';

export interface CameraSettings {
    columns: number | null;
    show3dView: boolean;
    layoutDirection: LayoutDirection;
}

export const StreamingViewPage = () => {
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
            <div className="streaming-page flex flex-col pos-rel overflow-hidden bg-dark" style={{
                padding: 8,
                flex: 1,
                height: '100%',
                width: '100%',
            }}>
                <SettingsOverlay
                    settings={settings}
                    onSettingsChange={handleSettingsChange}
                    onResetLayout={handleResetLayout}
                />

                <div className="preview-container-camera-and-3d flex-1 overflow-hidden">
                    {settings.show3dView ? (
                        <PanelGroup
                            key={`main-panels-${resetKey}-${settings.layoutDirection}`}
                            direction={settings.layoutDirection}
                        >
                            <Panel defaultSize={60} minSize={20}>
                                <div style={{height: '100%', overflow: 'auto'}}>
                                    <ErrorBoundary>
                                        <CameraViewsGrid manualColumns={settings.columns} resetKey={resetKey}/>
                                    </ErrorBoundary>
                                </div>
                            </Panel>

                            <PanelResizeHandle>
                                <div 
                                    className="resizable-component"
                                    style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    backgroundColor: 'var(--color-border-secondary)',
                                    transition: 'background-color 0.15s ease',
                                    cursor: isHorizontal ? 'col-resize' : 'row-resize',
                                    ...(isHorizontal
                                        ? {width: '6px', height: '100%', flexDirection: 'column' as const}
                                        : {height: '6px', width: '100%', flexDirection: 'row' as const}
                                    ),
                                }}>
                                    {[0, 1, 2].map((i) => (
                                        <div key={i} style={{
                                            width: 4,
                                            height: 4,
                                            borderRadius: '50%',
                                            backgroundColor: 'var(--color-text-disabled)',
                                            margin: isHorizontal ? '2px 0' : '0 2px',
                                            flexShrink: 0,
                                        }}/>
                                    ))}
                                </div>
                            </PanelResizeHandle>

                            <Panel className='realtime-3d-viewport-container'  defaultSize={40} minSize={10}>
                                <div className='realtime-3d-viewport' style={{height: '100%'}}>
                                    <ThreeJsCanvas/>
                                </div>
                            </Panel>
                        </PanelGroup>
                    ) : (
                        <div style={{height: '100%', overflow: 'auto'}}>
                            <ErrorBoundary>
                                <CameraViewsGrid manualColumns={settings.columns} resetKey={resetKey}/>
                            </ErrorBoundary>
                        </div>
                    )}
                </div>

                <footer style={{padding: 8, flexShrink: 0}}>
                    <Footer/>
                </footer>
            </div>
        </React.Fragment>
    );
};
