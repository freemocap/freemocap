import React, { useCallback, useState } from "react";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import { Footer } from "@/components/ui-components/Footer";
import { CameraViewsGrid } from "@/components/camera-views/CameraViewsGrid";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { ThreeJsCanvas } from "@/components/viewport3d/ThreeJsCanvas";
import { SettingsOverlay } from "@/components/ui-components/SettingsOverlay";

export type LayoutDirection = "vertical" | "horizontal";

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
    layoutDirection: "horizontal",
  });

  const handleSettingsChange = useCallback(
    (partial: Partial<CameraSettings>) => {
      setSettings((prev) => ({ ...prev, ...partial }));
    },
    [],
  );

  const handleResetLayout = useCallback(() => {
    setResetKey((v) => v + 1);
  }, []);

  const isHorizontal = settings.layoutDirection === "horizontal";

  return (
    <React.Fragment>
      <div className="streaming-page p-2 flex flex-col pos-rel flex-1 h-full w-full">
        <SettingsOverlay
          settings={settings}
          onSettingsChange={handleSettingsChange}
          onResetLayout={handleResetLayout}
        />

        <div className="flex-1 overflow-hidden">
          {settings.show3dView ? (
            <PanelGroup
              key={`main-panels-${resetKey}-${settings.layoutDirection}`}
              direction={settings.layoutDirection}
            >
              <Panel defaultSize={60} minSize={20}>
                <div className="streaming-page-camera-feed-container br-2 h-full overflow-y">
                  <ErrorBoundary>
                    <CameraViewsGrid
                      manualColumns={settings.columns}
                      resetKey={resetKey}
                    />
                  </ErrorBoundary>
                </div>
              </Panel>

              <PanelResizeHandle
                className="resizable-component"
                style={{
                  width: "4px",
                  cursor: "col-resize",
                  backgroundColor: "var(--color-surface-active)",
                }}
              />

              <Panel defaultSize={40} minSize={10}>
                <div className="h-full 3d-viewport-master">
                  <ThreeJsCanvas />
                </div>
              </Panel>
            </PanelGroup>
          ) : (
            <div className="h-full overflow-y">
              <ErrorBoundary>
                <CameraViewsGrid
                  manualColumns={settings.columns}
                  resetKey={resetKey}
                />
              </ErrorBoundary>
            </div>
          )}
        </div>

        {/* <footer className="p-2 flex-shrink-0">
          <Footer />
        </footer> */}
      </div>
    </React.Fragment>
  );
};
