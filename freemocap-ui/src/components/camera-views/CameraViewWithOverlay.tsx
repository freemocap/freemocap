import React, { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import IconButton from "@/components/ui-components/IconButton";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import { Row } from "@/components/ui-components/Row";
import SegmentedControl from "@/components/ui-components/SegmentedControl";
import ValueSelector from "@/components/ui-components/ValueSelector";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectCameraById } from "@/store/slices/cameras/cameras-selectors";
import {
  cameraDesiredConfigUpdated,
  autoApplyToggled,
} from "@/store/slices/cameras/cameras-slice";
import { camerasConnectOrUpdate } from "@/store/slices/cameras/cameras-thunks";
import {
  ROTATION_DEGREE_LABELS,
  ROTATION_OPTIONS,
  RotationValue,
} from "@/store/slices/cameras/cameras-types";
import { CameraView } from "./CameraView";

const EXPOSURE_MIN = -13;
const EXPOSURE_MAX = -4;

interface CameraViewWithOverlayProps {
  cameraIndex: number;
  cameraId: string;
  isLoading: boolean;
  isAutoApply: boolean;
}

export const CameraViewWithOverlay: React.FC<CameraViewWithOverlayProps> = ({
  cameraIndex,
  cameraId,
  isLoading,
  isAutoApply,
}) => {
  const dispatch = useAppDispatch();
  const { t } = useTranslation();
  const [showSettings, setShowSettings] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const camera = useAppSelector((state) => selectCameraById(state, cameraId));
  const desiredConfig = camera?.desiredConfig;

  useEffect(() => {
    if (!showSettings) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (
        overlayRef.current &&
        !overlayRef.current.contains(e.target as Node)
      ) {
        setShowSettings(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showSettings]);

  const rotation = (desiredConfig?.rotation as RotationValue) ?? -1;
  const exposure = desiredConfig?.exposure ?? -7;
  const exposureMode = desiredConfig?.exposure_mode ?? "MANUAL";

  const EXPOSURE_MODE_LABELS = { AUTO: t("auto"), MANUAL: t("custom") };
  const EXPOSURE_MODE_OPTIONS = Object.values(EXPOSURE_MODE_LABELS);

  const handleExposureModeChange = (label: string) => {
    const modeMap: Record<string, "AUTO" | "MANUAL"> = {
      [EXPOSURE_MODE_LABELS.AUTO]: "AUTO",
      [EXPOSURE_MODE_LABELS.MANUAL]: "MANUAL",
    };
    dispatch(
      cameraDesiredConfigUpdated({
        cameraId,
        config: { exposure_mode: modeMap[label] ?? "MANUAL" },
      }),
    );
  };

  const handleExposureValueChange = (value: number) => {
    dispatch(
      cameraDesiredConfigUpdated({
        cameraId,
        config: { exposure: value, exposure_mode: "MANUAL" },
      }),
    );
  };

  const handleApply = async () => {
    setIsApplying(true);
    try {
      await dispatch(camerasConnectOrUpdate()).unwrap();
    } catch {
      // error stored in redux state
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div className="pos-rel w-full h-full">
      <CameraView cameraIndex={cameraIndex} cameraId={cameraId} maxWidth />

      {/* Settings toggle button */}
      <div className="pos-abs top-6 right-6 z-10" ref={overlayRef}>
        <IconButton
          icon="settings-icon"
          className="icon icon-size-25"
          title={showSettings ? t("closeSettings") : t("camera.openSettings")}
          onClick={() => setShowSettings((prev) => !prev)}
          tooltip={true}
          tooltipPosition="pos-left"
          tooltipText={t("camera.settings")}
        />

        {showSettings && (
          <div className="camera-settings-container contextual camera-overylay-settings pos-abs top-30 right-6 flex flex-col z-10 br-2 border-1 border-black elevated-sharp bg-dark p-1 gap-1">
            <div className="w-full flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
              {/* Header */}
              <div className="subaction-header-container justify-content-space-between gap-1 br-1 flex items-center h-25 p-1">
                <p className="text-nowrap text-left bg-md text-darkgray">
                  {t("camera.settings")}
                </p>
              </div>

              {/* Rotate */}
              <Row label={t("camera.rotate")}>
                <SegmentedControl
                  options={ROTATION_OPTIONS.map((o: RotationValue) => ({
                    label: ROTATION_DEGREE_LABELS[o],
                    value: String(o),
                  }))}
                  value={String(rotation)}
                  onChange={(v) => {
                    dispatch(
                      cameraDesiredConfigUpdated({
                        cameraId,
                        config: { rotation: Number(v) as RotationValue },
                      }),
                    );
                  }}
                  size="sm"
                  className="segmented-control-sm bg-darkgray"
                />
              </Row>


              {/* Exposure mode dropdown */}
              <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
                <span className="text-sm">{t("camera.exposureMode")}</span>
                <NameDropdownSelector
                  key={exposureMode}
                  options={EXPOSURE_MODE_OPTIONS}
                  initialValue={EXPOSURE_MODE_LABELS[exposureMode as "AUTO" | "MANUAL"]}
                  onChange={handleExposureModeChange}
                />
              </div>

              {/* Exposure value — only when manual */}
              {exposureMode === "MANUAL" && (
                <div className="manual-exposure-group flex flex-row gap-1  p-1 justify-content-space-between">
                  <div className="flex flex-row items-center gap-1">
                    <span className="icon subcat-icon icon-size-20" />
                    <p className="text bg">{t("exposure")}</p>
                  </div>

                  <ValueSelector
                    value={exposure}
                    min={EXPOSURE_MIN}
                    max={EXPOSURE_MAX}
                    step={1}
                    onChange={handleExposureValueChange}
                    disabled={isLoading}
                  />
                </div>
              )}

          

              {/* Footer */}
              <div className="flex flex-col gap-1">
                <ToggleComponent
                  text={t("camera.autoApply")}
                  
                  isToggled={isAutoApply}
                  onToggle={() => dispatch(autoApplyToggled())}
                />
                <button
                  className={`button sm br-1 secondary flex-1${isAutoApply ? " disabled" : ""}`}

                  onClick={handleApply}
                  disabled={isApplying || isAutoApply}
                  title={t("camera.applyChanges")}
                >
                  <p
                    className="text md text-white"
                    
                  >
                    {isApplying ? t("camera.applying") : t("camera.apply")}
                  </p>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
