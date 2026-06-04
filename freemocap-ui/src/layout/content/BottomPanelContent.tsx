import * as React from 'react';
import {LogTerminal} from "@/components/log-terminal";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import TabbedBottomLeftPanel from "@/components/tabbed-bottom-panel/TabbedBottomLeftPanel";

export default function BottomPanelContent({isCollapsed}: { isCollapsed: boolean }) {
    return (
        <div className="bottom-info-container br-2 flex h-full">
            <PanelGroup className="console-area p-0" direction="horizontal" style={{ direction: "ltr" }}>
                <Panel className="camera-performance-metric-container bg-middark bg-darkgray p-1 br-1" defaultSize={30} minSize={15}>
                    <TabbedBottomLeftPanel isCollapsed={isCollapsed} />
                </Panel>
                <PanelResizeHandle className="info-panel-divider resizable-component" />
                <Panel className="server-logs-container text-nowrap bg-middark bg-darkgray p-1 br-1" defaultSize={70} minSize={20}>
                    <LogTerminal isCollapsed={isCollapsed} />
                </Panel>
            </PanelGroup>
        </div>
    );
}
