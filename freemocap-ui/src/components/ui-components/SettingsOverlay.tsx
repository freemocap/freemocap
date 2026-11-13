import {RealtimeProcessingButton} from '@/components/control-panels/realtime-panel/RealtimeProcessingButton';
import RealtimeProcessingSettings from '@/components/realtime-processing/RealtimeProcessingSettings';
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
import SegmentedControl from "@/components/ui-components/SegmentedControl";
import { Row } from "@/components/ui-components/Row";
import { useRealtimePipelineSync } from "@/hooks/useRealtimePipelineSync";


interface SettingsOverlayProps {
  settings: CameraSettings;
  onSettingsChange: (partial: Partial<CameraSettings>) => void;
  onResetLayout: () => void;
}

export const SettingsOverlay: React.FC<SettingsOverlayProps> = ({
  settings,
  onSettingsChange,
  onResetLayout,
}) => {
  const { connectedCameraIds } = useServer();
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [processingSettingsOpen, setProcessingSettingsOpen] = useState(false);
  const [isAuto, setIsAuto] = useState<boolean>(settings.columns === null);
  const [manualColumns, setManualColumns] = useState<number>(
    settings.columns ?? 2,
  );

  const {
    isConnected,
    isLoading: isPipelineLoading,
    toggleConnection,
  } = useRealtimePipelineSync();

  const handleLiveStreamClick = () => {
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
      <div data-onboarding="realtime:pipeline" className="streaming-bar-setting-action-bar z-2 pos-abs flex flex-row gap-3 top-0 right-0">
        <div className="live-action-buttons-container flex flex-row gap-4">

          {/* GROUP 3 */}
          <div className="p-1 live-action-buttons-group-3 flex flex-row items-center gap-3">

            <RealtimeProcessingButton connected={isConnected} loading={isPipelineLoading} onToggle={handleLiveStreamClick}/>
            <button type="button" className="button sm secondary br-1" onClick={() => setProcessingSettingsOpen(true)}>
              Processing settings
            </button>
            {processingSettingsOpen && <RealtimeProcessingSettings onClose={() => setProcessingSettingsOpen(false)}/>}
          </div>

        </div>

        <div className="modal-container stream-mode pos-rel">
          <IconButton
            icon={isOpen ? "close-icon" : "grid2-icon"}
            className="icon-size-32 br-2"
            onClick={() => setIsOpen(!isOpen)}
            title={isOpen ? t("closeSettings") : t("gridSettings")}
            tooltip={!isOpen}
            tooltipText="Grid Settings"
            tooltipPosition="pos-bottom-right"
          />

      {/* SETTINGS PANEL */}
      {isOpen && (
      <div
          className="bg-dark border-1 border-black elevated-sharp br-2 elevated-sharp flex flex-col gap-1 p-1 min-h-0"
          style={{
            position: "absolute",
            top: "100%",
            right: 0,
            marginTop: 8,
            zIndex: 999,
            minWidth: 260,
          }}
        >
        <div className="flex flex-col right-0 p-1 gap-1 bg-middark br-1 z-1">
              <Row label="Layout">

                <SegmentedControl
                     size="sm"
                  className="segmented-control-sm bg-darkgray"
                  value={settings.layoutDirection}
                  options={[
                    { label: "Horizontal", value: "horizontal" },
                    { label: "Vertical", value: "vertical" },
                  ]}
                  onChange={(value) => handleLayoutDirectionChange(value as LayoutDirection)}
                />
              </Row>
            <div className="flex pt-2 flex-row items-center w-full justify-content-space-between p-1">
              {/* <span className="icon grid4-icon icon-size-20" /> */}
              <p className="text bg">{t("gridColumns")}</p>
              <p className="text sm text-gray">
              {isAuto
                ? `Auto: ${autoColumns} Columns`
                : "Enter any positive number"}
            </p>
            </div>
          <div className="flex flex-col gap-2 align-end">

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

          
          </div>

          {/* <div
            style={{
              height: 1,
              backgroundColor: "var(--color-border-secondary)",
            }}
          /> */}

          <div className="pt-3 flex flex-col gap-1">
            <ToggleComponent
              text="3D Viewport"
              iconClass=""
              isToggled={settings.show3dView}
              onToggle={handle3dViewToggle}
            />
          </div>

          {settings.show3dView && (
            <>
              {/* <div
                style={{
                  height: 1,
                  backgroundColor: "var(--color-border-secondary)",
                }}
              /> */}

            </>
          )}
          </div>
        </div>
      )}
        </div>
      </div>
    </>
  );
};
