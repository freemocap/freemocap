import React, { useRef, useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";

import { CameraSettingsModal } from "./CameraSettingsModal";
import { ROTATION_DEGREE_LABELS, RotationValue, useAppDispatch } from "@/store";
import {
  cameraRealtimeToggled,
  cameraSelectionToggled,
} from "@/store/slices/cameras/cameras-slice";
import { Camera } from "@/store/slices/cameras/cameras-types";
import Checkbox from "@/components/ui-components/Checkbox";
import IconButton from "@/components/ui-components/IconButton";

interface CameraTreeItemProps {
  camera: Camera;
}

const getConfigSummary = (config: any): string[] => {
  const summary: string[] = [];

  if (!config) return summary;

  if (config.resolution?.width && config.resolution?.height) {
    summary.push(`${config.resolution.width}×${config.resolution.height}`);
  }

  if (config.framerate) {
    summary.push(`${parseFloat(config.framerate).toFixed(2)}fps`);
  }

  if (config.exposure !== undefined && config.exposure_mode === "MANUAL") {
    summary.push(`E:${config.exposure}`);
  }

  if (config.pixel_format && config.pixel_format !== "RGB") {
    summary.push(config.pixel_format);
  }

  if (config.rotation) {
    summary.push(ROTATION_DEGREE_LABELS[config.rotation as RotationValue]);
  }

  if (config.capture_fourcc) {
    summary.push(config.capture_fourcc);
  }

  return summary.filter((item) => item);
};

export const CameraTreeItem: React.FC<CameraTreeItemProps> = ({ camera }) => {
  const dispatch = useAppDispatch();
  const { t } = useTranslation();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [modalPos, setModalPos] = useState({ top: 80, left: 40 });
  const settingsBtnRef = useRef<HTMLButtonElement>(null);

  const handleToggleSelection = (
    e: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    e.stopPropagation();
    dispatch(cameraSelectionToggled(camera.id));
  };

  const handleToggleRealtime = (e: React.MouseEvent): void => {
    e.stopPropagation();
    dispatch(cameraRealtimeToggled(camera.id));
  };

  const handleOpenSettings = (e: React.MouseEvent): void => {
    e.stopPropagation();
    if (!settingsOpen && settingsBtnRef.current) {
      const rect = settingsBtnRef.current.getBoundingClientRect();
      setModalPos({ top: rect.bottom + 8, left: rect.right + 8 });
    }
    setSettingsOpen((prev) => !prev);
  };

  const configSummary = getConfigSummary(camera.desiredConfig);

  return (
    <div className="camera-item-row br-1 flex flex-col gap-1 m-1">
      <div className="camera-row-group flex flex-row gap-0 items-center">
        {/* Left: selection + realtime toggles */}
        <div className="flex flex-row checkbox-group">
          <div className="tooltip-wrapper pos-rel">
            <Checkbox
              label=""
              checked={camera.selected}
              onChange={handleToggleSelection}
              inputClassName={
                camera.connectionStatus === "connected" ? "streaming" : ""
              }
            />
            <div className="tooltip-container elevated-sharp pos-right p-01 br-2 bg-dark">
              <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
                <p className="text-white text md">
                  {camera.selected
                    ? "Remove from capture group"
                    : "Add to capture group"}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right: camera info + settings toggle */}
        <div
          className={clsx(
            "camera-settings-button button sm br-1 flex flex-col gap-1 flex-1 cursor-pointer p-1",
            settingsOpen && "selected-camera-feed",
            settingsOpen && "selected-camera-settings",
          )}
          onClick={handleOpenSettings}
        >
          <div className="flex flex-row items-center gap-2">
            <p
              className="text sm text-white text-nowrap"
              
            >
              Camera {camera.index}
            </p>
            <p
              className="text sm text-gray text-nowrap"
              style={{
                flex: "0 1 auto",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {camera.name}
            </p>
            <div className="flex-1" />

            <span className="icon icon-size-20 settings-icon"></span>
          </div>

          {/* Realtime status indicator + config chips */}
          <div className="flex flex-row items-center gap-1 flex-nowrap">
            <div className="tooltip-wrapper pos-rel flex-inline">
              <span
                className={clsx(
                  "icon icon-size-20 bg-middark br-1",
                  camera.realtimeEnabled ? "live-active-icon" : "live-icon",
                  camera.selected ? "cursor-pointer" : "disabled",
                )}
                onClick={camera.selected ? handleToggleRealtime : undefined}
              />
              <div className="tooltip-container elevated-sharp pos-right p-01 br-2 bg-dark">
                <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
                  <p className="text-white text md">
                    {camera.realtimeEnabled
                      ? "Remove from realtime pipeline"
                      : "Add to realtime pipeline"}
                  </p>
                </div>
              </div>
            </div>

            {configSummary.length > 0 && (
              <div className="flex flex-wrap gap-1 flex-nowrap">
                {configSummary.map((item) => (
                  <span key={item} className="tag camera-config-chip">
                    {item}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {settingsOpen && (
        <CameraSettingsModal
          camera={camera}
          initialPos={modalPos}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </div>
  );
};
