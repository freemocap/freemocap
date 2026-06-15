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
      <div className="streaming-bar-setting-action-bar z-2 pos-abs flex flex-row gap-3 top-0 right-0">
        <IconButton
          icon={isOpen ? "close-icon" : "settings-icon"}
          className="icon-size-25 br-2 bg-middark"
          onClick={() => setIsOpen(!isOpen)}
          title={isOpen ? t("closeSettings") : t("gridSettings")}
        />
      </div>

      {/* SETTINGS PANEL */}
      {isOpen && (
        <div
          className="bg-middark br-2 elevated-sharp flex flex-col gap-2 p-2"
          style={{
            position: "absolute",
            top: 0,
            right: 16,
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
    </>
  );
};
