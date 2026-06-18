import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ImperativePanelHandle,
  Panel,
  PanelGroup,
  PanelResizeHandle,
} from "react-resizable-panels";
import { useLocation } from "react-router-dom";
import { SidePanelContent } from "@/layout/content/SidePanelContent";
import BottomPanelContent from "@/layout/content/BottomPanelContent";
import { useMenuActions } from "@/hooks/useMenuActions";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { RecordingCompleteDialog } from "@/components/control-panels/recording-info-panel/RecordingCompleteDialog";
import { MainNavTabs } from "@/components/ui-components/MainNavTabs";
import { FloatingOnboarding } from "@/hooks/floatingOnboarding";
import PromptTooltip from "@/components/ui-components/promptTooltip";
import { useServer } from "@/services/server/ServerContextProvider";
import { useAppSelector } from "@/store";
import { selectIsLoading } from "@/store/slices/cameras/cameras-selectors";

export const BasePanelLayout = ({
  children,
  onOpenWelcome,
}: {
  children?: React.ReactNode;
  onOpenWelcome?: () => void;
}) => {
  const leftPanelRef = useRef<ImperativePanelHandle>(null);
  const bottomPanelRef = useRef<ImperativePanelHandle>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isBottomCollapsed, setIsBottomCollapsed] = useState(true);

  const { isConnected, isFailed, connectedCameraIds } = useServer();
  const location = useLocation();
  const isCamerasLoading = useAppSelector(selectIsLoading);

  useEffect(() => {
    bottomPanelRef.current?.collapse();
  }, []);

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
  const handleBottomPanelCollapse = useCallback(
    () => setIsBottomCollapsed(true),
    [],
  );
  const handleBottomPanelExpand = useCallback(
    () => setIsBottomCollapsed(false),
    [],
  );

  useMenuActions({ onToggleSidebar: handleToggleCollapse });
  useKeyboardShortcuts();

  return (
    <div
      className="main-app-container flex flex-col"
      style={{ height: "100vh" }}
    >
      <FloatingOnboarding
        target='[data-onboarding="connection:server-connection"]'
        className="z-110i"
      >
        <PromptTooltip
          className={isFailed ? "" : "loading"}
          show={!isConnected}
          title={isFailed ? "Service Unavailable" : "Connecting..."}
          text={isFailed
            ? "Make sure you have the service running"
            : "Websocket connecting, app functions will be available once connection is made"}
          position="pos-bottom"
          variant={isFailed ? "warning" : "default"}
          onClose={() => {}}
        />
      </FloatingOnboarding>

      <FloatingOnboarding target='[data-onboarding="camera:connect-camera"]'>
        <PromptTooltip
          show={
            location.pathname === '/streaming' &&
            connectedCameraIds.length === 0 &&
            !isCamerasLoading
          }
          title="Connect Cameras"
          text="Make sure you have at least one camera plugged in, then hit Connect to start streaming."
          position="pos-right"
          variant="boarding"
          onClose={() => {}}
        />
      </FloatingOnboarding>

      <PanelGroup className="app-container flex-1" direction="vertical">
        {/* Top section (horizontal panels) */}
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
              <SidePanelContent
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
            <Panel className="right-side-panel" defaultSize={76} minSize={10}>
              <div className="flex flex-col h-full pos-rel bg-darkgray br-2">
                <MainNavTabs />
                <div className="flex-1 min-h-0 mt-45">{children}</div>
              </div>
              <RecordingCompleteDialog />
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
