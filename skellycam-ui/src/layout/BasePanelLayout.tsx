// skellycam-ui/src/layout/BasePanelLayout.tsx
import React, {useCallback, useEffect, useRef, useState} from "react";
import {ImperativePanelHandle, Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {useNavigate} from "react-router-dom";
import {LeftSidePanelContent} from "@/components/ui-components/LeftSidePanelContent";
import BottomPanelContent from "@/components/ui-components/BottomPanelContent";
import {useMenuActions} from "@/hooks/useMenuActions";
import {useKeyboardShortcuts} from "@/hooks/useKeyboardShortcuts";
import {FloatingOnboarding} from "@/hooks/floatingOnboarding";
import PromptTooltip from "@/components/ui-components/promptTooltip";
import {useServer} from "@/services/server/ServerContextProvider";
import {ConnectionState} from "@/services/server/server-helpers/websocket-connection";

export const BasePanelLayout = ({children, welcomeOpen = false, onOpenWelcome}: { children: React.ReactNode; welcomeOpen?: boolean; onOpenWelcome?: () => void }) => {
    const { connectionState, connectedCameraIds } = useServer();
    const showServiceUI = connectionState !== ConnectionState.CONNECTED;
    const isFailed = connectionState === ConnectionState.FAILED
        || connectionState === ConnectionState.RECONNECTING;
    const showConnectCameras = !welcomeOpen && connectionState === ConnectionState.CONNECTED && connectedCameraIds.length === 0;

    const navigate = useNavigate();
    const prevCameraCountRef = useRef(0);
    useEffect(() => {
        if (prevCameraCountRef.current === 0 && connectedCameraIds.length > 0) {
            navigate('/cameras');
        }
        prevCameraCountRef.current = connectedCameraIds.length;
    }, [connectedCameraIds.length]);

    const leftPanelRef = useRef<ImperativePanelHandle>(null);
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

    useMenuActions({ onToggleSidebar: handleToggleCollapse });
    useKeyboardShortcuts();

    return (
      <div
        className="main-app-container"
        style={{ display: "flex", flexDirection: "column", height: "100vh" }}
      >
        <FloatingOnboarding
          target='[data-warning="service-unavailable"]'
          className="z-110i"
        
        >
                    <PromptTooltip
                        show={showServiceUI}
                        title={isFailed ? "Service Unavailable" : "Connecting..."}
                        text={isFailed
                            ? "Make sure you have the service running"
                            : "Websocket connecting, app functions will be available once connection is made"}
                        button={isFailed}
                        buttonText="Learn how to set up"
                        onButtonClick={() => window.open("https://github.com/freemocap/freemocap", "_blank")}
                        position="pos-bottom"
                        variant={isFailed ? "warning" : "default"}
                        className={isFailed ? "" : "loading"}
                        onClose={() => {}}
                    />
        </FloatingOnboarding>
        <FloatingOnboarding
          target='[data-onboarding="connect-cameras"]'
          
          
        >
                    <PromptTooltip
                        show={showConnectCameras}
                        title="Connect Cameras"
                        text="Make sure you have at least one camera plugged in, then hit Connect to start streaming."
                        position="pos-right"
                        variant="boarding"
                        onClose={() => {}}
                    />
        </FloatingOnboarding>
        <PanelGroup
          className="app-container"
          direction="vertical"
          style={{ flex: 1 }}
        >
          <Panel className="app-container-inner" defaultSize={87} minSize={20}>
            <PanelGroup
              className="pos-rel app-container-sub pr-1 pl-1 pt-1 pb-0"
              direction="horizontal"
              style={{ direction: "ltr" }}
            >
              <Panel
                className="left-side-panel p-1 action-container bg-darkgray br-2 border-mid-black border-1"
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
                  onOpenWelcome={onOpenWelcome}
                />
              </Panel>
              <PanelResizeHandle
                className="resizable-component"
                style={{
                  width: "4px",
                  cursor: "col-resize",
                  backgroundColor: "var(--color-surface-active)",
                }}
              />
              <Panel className="right-side-panel" defaultSize={60} minSize={10}>
                {children}
              </Panel>
            </PanelGroup>
          </Panel>

          <PanelResizeHandle
            className="resizable-component"
            style={{
              height: "4px",
              cursor: "row-resize",
              backgroundColor: "var(--color-surface-active)",
            }}
          />

          <Panel
            className="console-area pr-1 pl-1 pb-1"
            collapsible
            defaultSize={13}
            minSize={10}
            collapsedSize={4}
            onCollapse={() => setIsBottomCollapsed(true)}
            onExpand={() => setIsBottomCollapsed(false)}
          >
            <BottomPanelContent isCollapsed={isBottomCollapsed} />
          </Panel>
        </PanelGroup>
      </div>
    );
};
