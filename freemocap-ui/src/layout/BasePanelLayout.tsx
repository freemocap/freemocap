// freemocap-ui/src/layout/BasePanelLayout.tsx
import React, {useCallback, useRef, useState} from "react";
import {ImperativePanelHandle, Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {LeftSidePanelContent} from "@/components/ui-components/LeftSidePanelContent";
import BottomPanelContent from "@/components/ui-components/BottomPanelContent";
import {useTheme} from "@mui/material/styles";
import {Box} from "@mui/material";
import {useMenuActions} from "@/hooks/useMenuActions";
import {useKeyboardShortcuts} from "@/hooks/useKeyboardShortcuts";

export const BasePanelLayout = ({children}: { children: React.ReactNode }) => {
    const theme = useTheme();
    const leftPanelRef = useRef<ImperativePanelHandle>(null);
    const [isCollapsed, setIsCollapsed] = useState(false);

    const handleToggleCollapse = useCallback(() => {
        const panel = leftPanelRef.current;
        if (!panel) return;

        if (panel.isCollapsed()) {
            panel.expand();
        } else {
            panel.collapse();
        }
    }, []);

    const handlePanelCollapse = useCallback(() => {
        setIsCollapsed(true);
    }, []);

    const handlePanelExpand = useCallback(() => {
        setIsCollapsed(false);
    }, []);

    // Connect native menu actions to the app
    useMenuActions({ onToggleSidebar: handleToggleCollapse });

    // Register global keyboard shortcuts (Ctrl+Shift+L, Shift+Space, etc.)
    useKeyboardShortcuts();

    return (
        <Box sx={{display: 'flex', flexDirection: 'column', height: '100vh'}}>
            <PanelGroup
                direction="vertical"
                style={{flex: 1}}
            >
                {/* Top section (horizontal panels) */}
                <Panel defaultSize={87} minSize={20}>
                    <PanelGroup direction="horizontal" style={{direction: "ltr"}}>
                        <Panel
                            ref={leftPanelRef}
                            collapsible
                            defaultSize={24}
                            minSize={10}
                            collapsedSize={3}
                            onCollapse={handlePanelCollapse}
                            onExpand={handlePanelExpand}
                        >
                            <LeftSidePanelContent
                                isCollapsed={isCollapsed}
                                onToggleCollapse={handleToggleCollapse}
                            />
                        </Panel>
                        {/* Horizontal Resize Handle */}
                        <PanelResizeHandle
                            style={{
                                width: "4px",
                                cursor: "col-resize",
                                backgroundColor: theme.palette.primary.light,
                            }}
                        />

                        {/* Main/Central Content Panel */}
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
