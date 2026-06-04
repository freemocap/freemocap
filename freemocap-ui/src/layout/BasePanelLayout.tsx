import React, {useCallback, useRef, useState} from "react";
import {ImperativePanelHandle, Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {SidePanelContent} from "@/layout/content/SidePanelContent";
import BottomPanelContent from "@/layout/content/BottomPanelContent";
import {useMenuActions} from "@/hooks/useMenuActions";
import {useKeyboardShortcuts} from "@/hooks/useKeyboardShortcuts";
import {RecordingCompleteDialog} from "@/components/control-panels/recording-info-panel/RecordingCompleteDialog";
import {MainNavTabs} from "@/components/ui-components/MainNavTabs";


export const BasePanelLayout = ({children}: { children?: React.ReactNode }) => {
    const leftPanelRef = useRef<ImperativePanelHandle>(null);
    const bottomPanelRef = useRef<ImperativePanelHandle>(null);
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isBottomCollapsed, setIsBottomCollapsed] = useState(false);

    const handleToggleCollapse = useCallback(() => {
        const panel = leftPanelRef.current;
        if (!panel) return;
        if (panel.isCollapsed()) {
            panel.expand();
        } else {
            panel.collapse();
        }
    }, []);

    const handlePanelCollapse = useCallback(() => setIsCollapsed(true), []);
    const handlePanelExpand = useCallback(() => setIsCollapsed(false), []);
    const handleBottomPanelCollapse = useCallback(() => setIsBottomCollapsed(true), []);
    const handleBottomPanelExpand = useCallback(() => setIsBottomCollapsed(false), []);

    useMenuActions({ onToggleSidebar: handleToggleCollapse });
    useKeyboardShortcuts();

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            <PanelGroup direction="vertical" style={{ flex: 1 }}>
                {/* Top section (horizontal panels) */}
                <Panel defaultSize={87} minSize={20}>
                    <PanelGroup
                        className="pos-rel pr-1 pl-1 pt-1 pb-0"
                        direction="horizontal"
                        style={{ direction: "ltr" }}
                    >
                        <Panel
                            className="left-side-panel p-1 bg-darkgray br-2 border-mid-black border-1"
                            ref={leftPanelRef}
                            collapsible
                            defaultSize={24}
                            minSize={10}
                            collapsedSize={3}
                            onCollapse={handlePanelCollapse}
                            onExpand={handlePanelExpand}
                        >
                            <SidePanelContent />
                        </Panel>
                        <PanelResizeHandle
                            className="resizable-component"
                            style={{ width: "4px", cursor: "col-resize" }}
                        />
                        <Panel className="right-side-panel" defaultSize={76} minSize={10}>
                            <MainNavTabs />
                            {children}
                            <RecordingCompleteDialog />
                        </Panel>
                    </PanelGroup>
                </Panel>

                <PanelResizeHandle
                    className="resizable-component"
                    style={{ height: "4px", cursor: "row-resize" }}
                />

                <Panel
                    className="console-area pr-1 pl-1 pb-1"
                    ref={bottomPanelRef}
                    collapsible
                    defaultSize={13}
                    minSize={10}
                    collapsedSize={4}
                    onCollapse={handleBottomPanelCollapse}
                    onExpand={handleBottomPanelExpand}
                >
                    <BottomPanelContent isCollapsed={isBottomCollapsed} />
                </Panel>
            </PanelGroup>
        </div>
    );
};
