  import React, { useState } from "react";
  import { useServer } from "@/services/server/ServerContextProvider";
  import { useTranslation } from "react-i18next";
  import type {
    CameraSettings,
    LayoutDirection,
  } from "@/pages/StreamingViewPage";
  import ToggleComponent from "@/components/ui-components/ToggleComponent";
  import IconButton from "@/components/ui-components/IconButton";

  interface SettingsOverlayProps {
    settings: CameraSettings;
    onSettingsChange: (partial: Partial<CameraSettings>) => void;
    onResetLayout: () => void;
  }

  type ActiveState = {
    twod: boolean;
    charuco: boolean;
    skeleton: boolean;
    trackingSettings: boolean;

    threed: boolean;
    triangulate: boolean;
    skeletonFilter: boolean;
    filterSettings: boolean;

    live: boolean;
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
      twod: false,
      charuco: false,
      skeleton: false,
      trackingSettings: false,

      threed: false,
      triangulate: false,
      skeletonFilter: false,
      filterSettings: false,

      live: false,
    });

    const toggleActive = (key: keyof ActiveState) => {
      setActive((prev) => ({
        ...prev,
        [key]: !prev[key],
      }));
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

    const handleColumnsChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      const value = parseInt(event.target.value);
      if (!isNaN(value) && value > 0) {
        setManualColumns(value);
        if (isAuto) setIsAuto(false);
        onSettingsChange({ columns: value });
      }
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
          <div className="live-action-buttons-container flex flex-row gap-32">

            {/* GROUP 1 */}
            <div className="live-action-buttons-group-1 flex flex-row items-center gap-1">

              <IconButton
                icon={active.twod ? "twodtracking-active-icon" : "twodtracking-icon"}
                onClick={() => toggleActive("twod")}
                tooltip
                tooltipText="2D Tracking"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.twod ? "active" : ""}`}
              />

              <IconButton
                icon={active.charuco ? "charuco-active-icon" : "charuco-icon"}
                onClick={() => toggleActive("charuco")}
                tooltip
                tooltipText="Charuco Board"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.charuco ? "active" : ""}`}
              />

              <IconButton
                icon={active.skeleton ? "skeleton-active-icon" : "skeleton-icon"}
                onClick={() => toggleActive("skeleton")}
                tooltip
                tooltipText="Skeleton Setup"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.skeleton ? "active" : ""}`}
              />

              <IconButton
                icon={active.trackingSettings ? "settings-icon" : "settings-icon"}
                onClick={() => toggleActive("trackingSettings")}
                tooltip
                tooltipText="Tracking Settings"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.trackingSettings ? "active" : ""}`}
              />
            </div>

            {/* GROUP 2 */}
            <div className="live-action-buttons-group-2 flex flex-row items-center gap-1">

              <IconButton
                icon={active.threed ? "threedtracking-active-icon" : "threedtracking-icon"}
                onClick={() => toggleActive("threed")}
                tooltip
                tooltipText="3D Tracking"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.threed ? "active" : ""}`}
              />

              <IconButton
                icon={active.triangulate ? "triangulate-active-icon" : "triangulate-icon"}
                onClick={() => toggleActive("triangulate")}
                tooltip
                tooltipText="Point Triangulation"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.triangulate ? "active" : ""}`}
              />

              <IconButton
                icon={active.skeletonFilter ? "skeletonfilter-active-icon" : "skeletonfilter-icon"}
                onClick={() => toggleActive("skeletonFilter")}
                tooltip
                tooltipText="Skeleton Filter"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.skeletonFilter ? "active" : ""}`}
              />

              <IconButton
                icon={active.filterSettings ? "settings-icon" : "settings-icon"}
                onClick={() => toggleActive("filterSettings")}
                tooltip
                tooltipText="Filter Settings"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.filterSettings ? "active" : ""}`}
              />
            </div>

            {/* GROUP 3 */}
            <div className="live-action-buttons-group-3 flex flex-row items-center gap-1">

              <IconButton
                icon={active.live ? "live-active-icon" : "live-icon"}
                onClick={() => toggleActive("live")}
                tooltip
                tooltipText="Live Stream"
                tooltipPosition="pos-bottom"
                disabled={false}
                className={`icon-size-25 ${active.live ? "active" : ""}`}
              />
            </div>

          </div>

          <button
            className="button icon-button br-2 bg-middark elevated-sharp"
            onClick={() => setIsOpen(!isOpen)}
            title={isOpen ? t("closeSettings") : t("gridSettings")}
          >
            <span
              className={`icon icon-size-20 ${
                isOpen ? "close-icon" : "settings-icon"
              }`}
            />
          </button>
        </div>

        {/* SETTINGS PANEL */}
        {isOpen && (
          <div
            className="bg-middark br-2 elevated-sharp flex flex-col gap-2 p-2"
            style={{
              position: "absolute",
              top: 70,
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

              <div className="input-with-unit flex-1">
                <input
                  type="number"
                  className="input-field numeric-input text md"
                  value={isAuto ? autoColumns : manualColumns}
                  onChange={handleColumnsChange}
                  min={1}
                  step={1}
                />
                <span className="unit-label text sm text-gray">
                  {t("columns")}
                </span>
              </div>

              <p className="text sm text-gray">
                {isAuto
                  ? `Auto-detected: ${autoColumns}`
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