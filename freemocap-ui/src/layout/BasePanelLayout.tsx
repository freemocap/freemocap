// freemocap-ui/src/layout/BasePanelLayout.tsx
import React from "react";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {LeftSidePanelContent} from "@/components/ui-components/LeftSidePanelContent";
import BottomPanelContent from "@/components/ui-components/BottomPanelContent";
import {useTheme} from "@mui/material/styles";
import {Box} from "@mui/material";
import {useLocation} from "react-router-dom";

export const BasePanelLayout = ({children}: { children: React.ReactNode }) => {
    const theme = useTheme();
    const location = useLocation();

    return (
        <Box sx={{display: 'flex', flexDirection: 'column', height: '100vh'}}>
            <PanelGroup
                direction="vertical"
                style={{flex: 1}}
            >
                {/* Top section (horizontal panels) - 80% height */}
                <Panel defaultSize={87} minSize={20}>
                    <PanelGroup direction="horizontal">
                        <Panel collapsible defaultSize={24} minSize={10} collapsedSize={4}>
                            <LeftSidePanelContent/>
                        </Panel>
                        {/* Horizontal Resize Handle */}
                        <PanelResizeHandle
                            style={{
                                width: "4px",
                                cursor: "col-resize",
                                backgroundColor: theme.palette.primary.light,
                            }}
                        />

                        {/*Main/Central Content Panel*/}
                        <Panel defaultSize={76} minSize={10}>
                            {children}
                        </Panel>
                    </PanelGroup>
                </Panel>

                {/* Vertical Resize Handle */}
                <PanelResizeHandle
                    style={{
                        height: "4px",
                        cursor: "row-resize",
                        backgroundColor: theme.palette.primary.light,
                    }}
                />

                <Panel collapsible defaultSize={13} minSize={10} collapsedSize={4}>
                    <BottomPanelContent/>
                </Panel>
            </PanelGroup>
        </Box>
    );
};
