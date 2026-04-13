// freemocap-ui/src/components/ui-components/BottomPanelContent.tsx
import * as React from 'react';
import Box from '@mui/material/Box';
import {LogTerminal} from "@/components/LogTerminal";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {useTheme} from "@mui/material/styles";
import TabbedBottomLeftPanel from "@/components/tabbed-bottom-panel/TabbedBottomLeftPanel";

export default function BottomPanelContent() {
    const theme = useTheme();

    return (
        <Box sx={{width: '100%', height: '100%'}}>
            <PanelGroup direction="horizontal" style={{direction: "ltr"}}>
                {/* Framerate Viewer Panel */}
                <Panel defaultSize={30} minSize={20}>
                    <Box sx={{height: '100%', overflow: 'auto'}}>
                        <TabbedBottomLeftPanel/>
                    </Box>
                </Panel>

                {/* Resize Handle */}
                <PanelResizeHandle
                    style={{
                        width: "4px",
                        cursor: "col-resize",
                        backgroundColor: theme.palette.primary.light,
                    }}
                />

                {/* Logs Terminal Panel */}
                <Panel defaultSize={70} minSize={20}>
                    <Box sx={{height: '100%', overflow: 'auto'}}>
                        <LogTerminal/>
                    </Box>
                </Panel>
            </PanelGroup>
        </Box>
    );
}
