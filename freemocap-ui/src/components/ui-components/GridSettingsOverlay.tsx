import React, { useState } from "react";
import { useServer } from "@/services/server/ServerContextProvider";
import { useTranslation } from "react-i18next";
import type {
  CameraSettings,
  LayoutDirection,
} from "@/pages/StreamingViewPage";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";
import IconButton from "@/components/ui-components/IconButton";
import SegmentedControl from "@/components/ui-components/SegmentedControl";
import { Row } from "@/components/ui-components/Row";

interface GridSettingsOverlayProps {
  settings: CameraSettings;
  onSettingsChange: (partial: Partial<CameraSettings>) => void;
}

export const GridSettingsOverlay: React.FC<GridSettingsOverlayProps> = ({
  settings,
  onSettingsChange,
}) => {
  const { connectedCameraIds } = useServer();
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isAuto, setIsAuto] = useState<boolean>(settings.columns === null);
  const [manualColumns, setManualColumns] = useState<number>(
    settings.columns ?? 2,
  );

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
      <div data-onboarding="realtime:pipeline" className="streaming-bar-setting-action-bar z-2 pos-abs flex flex-row gap-0 top-0 right-0">
        <div className="live-action-buttons-container flex flex-row gap-4">
          
        
          <div className="grid-settings-button-playback-model live-action-buttons-group-2 flex flex-row items-center gap-1">
            <IconButton
              
              icon={isOpen ? "close-icon" : "grid2-icon"}
              className="icon-size-32 br-2"
              onClick={() => setIsOpen(!isOpen)}
              title={isOpen ? t("closeSettings") : t("gridSettings")}
              tooltip
              tooltipText={t("gridSettings")}
              tooltipPosition="pos-bottom-right"
            />
          </div>
        </div>

        <div className="modal-container stream-mode pos-rel">
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
                <Row label={t("layout.layout")}>

                  <SegmentedControl
                    size="sm"
                    className="segmented-control-sm bg-darkgray"
                    value={settings.layoutDirection}
                    options={[
                      { label: t("layout.horizontal"), value: "horizontal" },
                      { label: t("layout.vertical"), value: "vertical" },
                    ]}
                    onChange={(value) => handleLayoutDirectionChange(value as LayoutDirection)}
                  />
                </Row>
                <div className="flex pt-2 flex-row items-center w-full justify-content-space-between p-1">
                  {/* <span className="icon grid4-icon icon-size-20" /> */}
                  <p className="text bg">{t("gridColumns")}</p>
                  <p className="text sm text-gray">
                    {isAuto
                      ? t("autoColumns", {count: autoColumns})
                      : t("enterPositiveNumber")}
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
                    text={t("viewport.threeDimensional")}
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
