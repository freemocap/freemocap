import * as React from 'react';
import {LogTerminal} from "@/components/log-terminal";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import TabbedBottomLeftPanel from "@/components/tabbed-bottom-panel/TabbedBottomLeftPanel";

export default function BottomPanelContent({isCollapsed}: { isCollapsed: boolean }) {
    return (
        <div className="w-full h-full">
            <PanelGroup direction="horizontal" style={{ direction: "ltr" }}>
                <Panel defaultSize={30} minSize={20}>
                    <div className="h-full overflow-y">
                        <TabbedBottomLeftPanel isCollapsed={isCollapsed} />
                    </div>
                </Panel>
                <PanelResizeHandle
                    className="resizable-component"
                    style={{ width: "4px", cursor: "col-resize" }}
                />
                <Panel defaultSize={70} minSize={20}>
                    <div className="h-full overflow-y">
                        <LogTerminal isCollapsed={isCollapsed} />
                    </div>
                </Panel>
            </PanelGroup>
        </div>
    );
}
