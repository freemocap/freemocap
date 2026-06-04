// skellycam-ui/src/components/ui-components/BottomPanelContent.tsx
import React from 'react';
import {useLocation} from "react-router-dom";
import {LogTerminal} from "@/components/LogTerminal";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import FramerateViewerPanel from "@/components/framerate-viewer/FrameRateViewer";

export default function BottomPanelContent({ isCollapsed = false }: { isCollapsed?: boolean }) {
    const location = useLocation();
    const isPlayback = location.pathname.startsWith('/playback');

    return (
        <div className="bottom-info-container br-2 flex h-full">
            {isPlayback ? (
                <div className="server-logs-container text-nowrap bg-middark bg-darkgray p-1 br-1 w-full h-full">
                    <LogTerminal isCollapsed={isCollapsed} />
                </div>
            ) : (
                <PanelGroup className="console-area p-0" direction="horizontal" style={{direction: "ltr"}}>
                    <Panel className="camera-performance-metric-container bg-middark bg-darkgray p-1 br-1" defaultSize={30} minSize={15}>
                        <FramerateViewerPanel isCollapsed={isCollapsed} />
                    </Panel>

                    <PanelResizeHandle className="info-panel-divider resizable-component" />

                    <Panel className="server-logs-container text-nowrap bg-middark bg-darkgray p-1 br-1" defaultSize={70} minSize={20}>
                        <LogTerminal isCollapsed={isCollapsed} />
                    </Panel>
                </PanelGroup>
            )}
        </div>
    );
}
