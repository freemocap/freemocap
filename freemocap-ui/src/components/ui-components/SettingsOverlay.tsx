import React, { useState } from "react";
import { useServer } from "@/services/server/ServerContextProvider";
import { useTranslation } from "react-i18next";
import type {
  CameraSettings,
  LayoutDirection,
} from "@/pages/StreamingViewPage";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import IconButton from "@/components/ui-components/IconButton";
import ValueSelector from "@/components/ui-components/ValueSelector";
import { useRealtimePipelineSync } from "@/hooks/useRealtimePipelineSync";

import RTPMediaPipeDetectorSettings from "@/components/pipeline-progress/realtime/realtimepipeline-mediapipedetector-settings";
import RTPthreeDReconstructionSettings from "@/components/pipeline-progress/realtime/realtimepipeline-3dreconstruction-settings";
import RTPPipelineActionsFlyout from "@/components/pipeline-progress/realtime/realtimepipeline-actions-flyout";

interface SettingsOverlayProps {
  settings: CameraSettings;
  onSettingsChange: (partial: Partial<CameraSettings>) => void;
  onResetLayout: () => void;
}

type ActiveState = {
  trackingSettings: boolean;
  filterSettings: boolean;
  pipelineSettings: boolean;
};

export const SettingsOverlay: React.FC<SettingsOverlayProps> = ({
  settings,
  onSettingsChange,
  onResetLayout,
}) => {
  const { connectedCameraIds } = useServer();
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isAuto, setIsAuto] = useState<boolean>(settings.columns === null);
  const [manualColumns, setManualColumns] = useState<number>(
    settings.columns ?? 2,
  );

  const [active, setActive] = useState<ActiveState>({
    trackingSettings: false,
    filterSettings: false,
    pipelineSettings: false,
  });

  const toggleActive = (key: keyof ActiveState) => {
    setActive((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const {
    pipelineConfig,
    cameraNodeConfig,
    aggregatorConfig,
    applyOrUpdatePipelineConfig,
    isConnected,
    isLoading: isPipelineLoading,
    canConnect,
    canDisconnect,
    toggleConnection,
  } = useRealtimePipelineSync();

  const charucoEnabled = cameraNodeConfig.charuco_tracking_enabled;
  const skeletonEnabled = cameraNodeConfig.skeleton_tracking_enabled;
  const triangulateEnabled = aggregatorConfig.triangulation_enabled;
  const filterEnabled = aggregatorConfig.filter_enabled;

  const handleCharucoToggle = () =>
    applyOrUpdatePipelineConfig({
      ...pipelineConfig,
      camera_node_config: { ...cameraNodeConfig, charuco_tracking_enabled: !charucoEnabled },
    });

  const handleSkeletonToggle = () =>
    applyOrUpdatePipelineConfig({
      ...pipelineConfig,
      camera_node_config: { ...cameraNodeConfig, skeleton_tracking_enabled: !skeletonEnabled },
    });

  const handleTriangulateToggle = () =>
    applyOrUpdatePipelineConfig({
      ...pipelineConfig,
      aggregator_config: { ...aggregatorConfig, triangulation_enabled: !triangulateEnabled },
    });

  const handleFilterToggle = () =>
    applyOrUpdatePipelineConfig({
      ...pipelineConfig,
      aggregator_config: { ...aggregatorConfig, filter_enabled: !filterEnabled },
    });

  const liveClickable = canConnect || canDisconnect;

  const handleLiveButtonClick = () => {
    if (!liveClickable || isPipelineLoading) return;
    toggleConnection();
  };

  const getAutoColumns = (total: number): number => {
    if (total <= 1) return 1;
    if (total <= 4) return 2;
    if (total <= 9) return 3;
    return 4;
  };

  const autoColumns = getAutoColumns(connectedCameraIds.length);

  const handleAutoChange = (checked: boolean) => {
    setIsAuto(checked);
    onSettingsChange({ columns: checked ? null : manualColumns });
  };

  const handleColumnsChange = (value: number) => {
    setManualColumns(value);
    if (isAuto) setIsAuto(false);
    onSettingsChange({ columns: value });
  };

  const handle3dViewToggle = (checked: boolean) => {
    onSettingsChange({ show3dView: checked });
  };

  const handleLayoutDirectionChange = (newDirection: LayoutDirection) => {
    onSettingsChange({ layoutDirection: newDirection });
  };

  return (
    <>
      <div className="streaming-bar-setting-action-bar z-2 pos-abs flex flex-row gap-3 top-0 right-0">
        <div className="live-action-buttons-container flex flex-row gap-4">

          {/* GROUP 1 */}
          <div className="p-1 br-2 bg-gray live-action-buttons-group-1 flex flex-row items-center gap-1">

            <IconButton
              icon={skeletonEnabled ? "twodtracking-active-icon" : "twodtracking-icon"}
              onClick={handleSkeletonToggle}
              tooltip
              tooltipText="2D Tracking"
              tooltipPosition="pos-bottom"
              disabled={false}
              className={`icon-size-25 ${skeletonEnabled ? "active" : ""}`}
            />

            <IconButton
              icon={charucoEnabled ? "charuco-active-icon" : "charuco-icon"}
              onClick={handleCharucoToggle}
              tooltip
              tooltipText="Charuco Board"
              tooltipPosition="pos-bottom"
              disabled={false}
              className={`icon-size-25 ${charucoEnabled ? "active" : ""}`}
            />

            <div className="modal-container pos-rel">
              <IconButton
                icon={active.trackingSettings ? "skeleton-active-icon" : "skeleton-icon"}
                onClick={() => toggleActive("trackingSettings")}
                tooltip
                tooltipText="Skeleton Setup"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`is-menu icon-size-25 ${active.trackingSettings ? "active" : ""}`}
              />
              {/* RTP MediaPipe Settings Modal */}
              <RTPMediaPipeDetectorSettings
                open={active.trackingSettings}
                onClose={() => toggleActive("trackingSettings")}
              />
            </div>
          </div>

          {/* GROUP 2 */}
          <div className="p-1 br-2 bg-gray live-action-buttons-group-2 flex flex-row items-center gap-1">

            <IconButton
              icon={triangulateEnabled ? "threedtracking-active-icon" : "threedtracking-icon"}
              onClick={handleTriangulateToggle}
              tooltip
              tooltipText="3D Tracking"
              tooltipPosition="pos-bottom"
              disabled={false}
              className={`icon-size-25 ${triangulateEnabled ? "active" : ""}`}
            />

            <IconButton
              icon={filterEnabled ? "skeletonfilter-active-icon" : "skeletonfilter-icon"}
              onClick={handleFilterToggle}
              tooltip
              tooltipText="Skeleton Filter"
              tooltipPosition="pos-bottom"
              disabled={false}
              className={`icon-size-25 ${filterEnabled ? "active" : ""}`}
            />

            <div className="modal-container pos-rel">
              <IconButton
                icon={active.filterSettings ? "settings-icon" : "settings-icon"}
                onClick={() => toggleActive("filterSettings")}
                tooltip
                tooltipText="Filter Settings"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`is-menu icon-size-25 ${active.filterSettings ? "active" : ""}`}
              />
              {/* RTP 3D Reconstructions Settings Modal */}
              <RTPthreeDReconstructionSettings
                open={active.filterSettings}
                onClose={() => toggleActive("filterSettings")}
              />
            </div>
          </div>

          {/* GROUP 3 */}
          <div className="p-1 br-2 bg-gray live-action-buttons-group-3 flex flex-row items-center gap-1">
            <IconButton
              icon={isConnected ? "live-active-icon" : "live-icon"}
              onClick={handleLiveButtonClick}
              tooltip
              tooltipText={
                isConnected
                  ? "Disconnect pipeline"
                  : canConnect
                    ? "Connect pipeline"
                    : "Select cameras first"
              }
              tooltipPosition="pos-bottom"
              disabled={isPipelineLoading}
              style={!liveClickable && !isPipelineLoading ? { opacity: 0.5 } : undefined}
              className={`icon-size-25 ${isConnected ? "active" : ""}`}
            />

            <div className="modal-container pos-rel">
              <IconButton
                icon="settings-icon"
                onClick={() => toggleActive("pipelineSettings")}
                tooltip
                tooltipText="Pipeline Settings"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`is-menu icon-size-25 ${active.pipelineSettings ? "active" : ""}`}
              />
              <RTPPipelineActionsFlyout
                open={active.pipelineSettings}
                onClose={() => toggleActive("pipelineSettings")}
              />
            </div>
          </div>

        </div>

        <div className="modal-container pos-rel">
          <IconButton
            icon={isOpen ? "close-icon" : "settings-icon"}
            className="icon-size-25 br-2"
            onClick={() => setIsOpen(!isOpen)}
            title={isOpen ? t("closeSettings") : t("gridSettings")}
          />

      {/* SETTINGS PANEL */}
      {isOpen && (
        <div
          className="bg-middark br-2 elevated-sharp flex flex-col gap-2 p-2"
          style={{
            position: "absolute",
            top: "100%",
            right: 0,
            marginTop: 8,
            zIndex: 999,
            minWidth: 260,
          }}
        >
          <div className="flex flex-col gap-1">
            <div className="flex flex-row items-center gap-1">
              <span className="icon grid4-icon icon-size-20" />
              <p className="text bg text-white">{t("gridColumns")}</p>
            </div>

            <ToggleComponent
              text={t("auto")}
              isToggled={isAuto}
              onToggle={handleAutoChange}
            />

            <ValueSelector
              value={isAuto ? autoColumns : manualColumns}
              min={1}
              max={12}
              onChange={handleColumnsChange}
            />

            <p className="text sm text-gray">
              {isAuto
                ? `Auto-detected: ${autoColumns} Columns`
                : "Enter any positive number"}
            </p>
          </div>

          <div
            style={{
              height: 1,
              backgroundColor: "var(--color-border-secondary)",
            }}
          />

          <div className="flex flex-col gap-1">
            <ToggleComponent
              text="3D Viewport"
              iconClass="streaming-icon"
              isToggled={settings.show3dView}
              onToggle={handle3dViewToggle}
            />
          </div>

          {settings.show3dView && (
            <>
              <div
                style={{
                  height: 1,
                  backgroundColor: "var(--color-border-secondary)",
                }}
              />

              <div className="flex flex-col gap-1">
                <p className="text bg text-white">Layout</p>

                <div className="flex flex-row gap-1">
                  <button
                    className={`button sm flex-1 ${
                      settings.layoutDirection === "horizontal"
                        ? "primary"
                        : "secondary"
                    }`}
                    onClick={() =>
                      handleLayoutDirectionChange("horizontal")
                    }
                  >
                    <p className="text sm">Side by side</p>
                  </button>

                  <button
                    className={`button sm flex-1 ${
                      settings.layoutDirection === "vertical"
                        ? "primary"
                        : "secondary"
                    }`}
                    onClick={() =>
                      handleLayoutDirectionChange("vertical")
                    }
                  >
                    <p className="text sm">Stacked</p>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
        </div>
      </div>
    </>
  );
};