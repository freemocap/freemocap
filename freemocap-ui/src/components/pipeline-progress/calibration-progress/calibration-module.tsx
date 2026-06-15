import React, { useCallback, useMemo, useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import IconButton from "@/components/ui-components/IconButton";
import DropdownButton from "@/components/ui-components/DropdownButton.tsx";
import CalibrationSettings from "./calibration-settings";
import ButtonSm from "@/components/ui-components/ButtonSm";
import { useCalibration } from "@/hooks/useCalibration";
import { useElectronIPC, useServer } from "@/services";
import { useAppDispatch, useAppSelector } from "@/store";
import {
  calibrationAutoLoadDismissed,
  calibrationLoadedFromBundle,
  loadCalibrationToml,
  selectLoadedCalibration,
} from "@/store/slices/calibration";

type CalibrationSource = "record" | "import-videos" | "import-toml";

/**
 * Represents the current operating mode of the application.
 * - "streaming": real-time camera capture mode (all calibration options available, including "Record and Calibrate")
 * - "playback": video playback mode ("Record and Calibrate" option should be hidden from the dropdown)
 *
 * TODO[INTEGRATION]: Replace this dummy state with the actual mode from the app's
 * global state or server. For example, you might fetch this from:
 * - A Redux selector like `useAppSelector(selectAppMode)`
 * - An IPC call to the backend
 * - A context provider
 */
type AppMode = "streaming" | "playback";

const SOURCE_ICONS: Record<CalibrationSource, string> = {
  record: "record-icon",
  "import-videos": "importVideos-icon",
  "import-toml": "tomlfile-icon",
};

interface CalibrationModuleProps {
  isCalibrated?: boolean;
}

const CalibrationModule = ({
  isCalibrated: isCalibratedProp,
}: CalibrationModuleProps) => {
  const dispatch = useAppDispatch();
  const { api, isElectron } = useElectronIPC();
  const { connectedCameraIds } = useServer();
  const loadedCalibration = useAppSelector(selectLoadedCalibration);

  const noCamerasConnected = connectedCameraIds.length === 0;

  const {
    config,
    error,
    isLoading,
    isRecording,
    recordingProgress,
    canStartRecording,
    updateCalibrationConfig,
    setManualRecordingPath,
    dispatchStartCalibrationRecording,
    dispatchStopCalibrationRecording,
    calibrateSelectedRecording,
    clearError,
  } = useCalibration();

  const [showCalibrationSettings, setShowCalibrationSettings] = useState(false);
  const [calibrationSource, setCalibrationSource] =
    useState<CalibrationSource>("record");

  // Derive app mode from the current route
  const location = useLocation();
  const appMode: AppMode = location.pathname === "/playback" ? "playback" : "streaming";

  // Cycling calibration messages during recording
  const calibrationMessages = [
    "Hold up the calibration board",
    "Check all cameras have a clear view",
    "Recording in progress",
  ];
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    if (!isRecording) {
      setMessageIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % calibrationMessages.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [isRecording, calibrationMessages.length]);


  const isCalibrated = isCalibratedProp ?? !!loadedCalibration;

  const [calibrationPathDir, calibrationPathFilename] = useMemo(() => {
    const path = loadedCalibration?.path ?? "";
    const splitIndex =
      path.lastIndexOf("/") !== -1
        ? path.lastIndexOf("/")
        : path.lastIndexOf("\\");
    if (splitIndex === -1) return ["", path];
    return [path.slice(0, splitIndex + 1), path.slice(splitIndex + 1)];
  }, [loadedCalibration?.path]);

  const charucoTags = [
    `${config.charucoBoard.squares_x}x${config.charucoBoard.squares_y}`,
    `${config.charucoBoard.square_length_mm}mm`,
    config.solverMethod === "anipose" ? "Anipose" : "Pyceres",
  ];

  const handleToggleSettings = () => {
    setShowCalibrationSettings(!showCalibrationSettings);
  };

  const handleCloseSettings = () => {
    setShowCalibrationSettings(false);
  };

  const handleRecordAndCalibrate = useCallback(() => {
    setCalibrationSource("record");
    dispatch(calibrationAutoLoadDismissed(null));
    dispatchStartCalibrationRecording();
  }, [dispatch, dispatchStartCalibrationRecording]);

  const handleImportVideos = useCallback(async () => {
    if (!isElectron || !api) return;
    const result: string | null = await api.fileSystem.selectDirectory.mutate();
    if (result) {
      await setManualRecordingPath(result);
      setCalibrationSource("import-videos");
      dispatch(calibrationAutoLoadDismissed(null));
      calibrateSelectedRecording();
    }
  }, [
    api,
    isElectron,
    dispatch,
    setManualRecordingPath,
    calibrateSelectedRecording,
  ]);

  const handleImportToml = useCallback(async () => {
    if (!isElectron || !api) return;
    const result: string | null = await api.fileSystem.selectTomlFile.mutate();
    if (result) {
      setCalibrationSource("import-toml");
      dispatch(calibrationAutoLoadDismissed(null));
      dispatch(loadCalibrationToml({ path: result, force: true }));
    }
  }, [api, isElectron, dispatch]);

  const handleClearCalibration = useCallback(() => {
    if (loadedCalibration) {
      dispatch(calibrationAutoLoadDismissed(loadedCalibration.path));
    }
    dispatch(calibrationLoadedFromBundle(null));
  }, [dispatch, loadedCalibration]);

  /**
   * Whether the "Record and Calibrate" option should appear in the dropdown.
   *
   * - Streaming mode: show "Record and Calibrate" (real-time recording is possible).
   * - Playback mode: hide "Record and Calibrate" (not applicable when playing back videos).
   */
  const shouldShowRecordAndCalibrate = appMode === "streaming";

  /**
   * Build the dropdown items for the calibration dropdown.
   * The dropdown itself is always visible, but the "Record and Calibrate" option
   * is conditionally hidden in playback mode.
   */
  const dropdownItems = (
    <div className="flex flex-col gap-1 calibrate-module-dropdown-list">
      {/* 
        "Record and Calibrate" is only available in streaming mode.
        In playback mode, this option is hidden since recording doesn't make sense.
      */}
      {shouldShowRecordAndCalibrate && (
        <ButtonSm
          iconClass="record-icon"
          text="Record and Calibrate"
          className="full-width"
          textClass="text-align-left"
          onClick={handleRecordAndCalibrate}
          disabled={noCamerasConnected && !isLoading}
          tooltip={true}
          tooltipPosition="pos-right"
          tooltipText={
            noCamerasConnected ? "Connect cameras to record" : undefined
          }
        />
      )}
      <ButtonSm
        iconClass="importVideos-icon"
        text="Import Calibration videos"
        className="full-width"
        textClass="text-align-left"
        onClick={handleImportVideos}
        disabled={!isElectron || isLoading}
      />
      <ButtonSm
        iconClass="tomlfile-icon"
        text="Import .toml file"
        className="full-width"
        textClass="text-align-left"
        onClick={handleImportToml}
        disabled={!isElectron || isLoading}
      />
    </div>
  );

  const errorBanner = error && (
    <div className="toast-notification gap-4 error flex items-center justify-content-space-between elevated-sharp">
      <p className="text sm">{error}</p>
      <IconButton icon="close-icon" onClick={clearError} />
    </div>
  );

  // Recording in progress
  if (isRecording) {
    return (
      <div className="calibration-module-recording flex flex-col p-1 bg-middark br-1 pos-rel gap-1">
        {errorBanner}
        <div className="flex flex-row items-center">
          <div className="flex flex-col flex-1 justify-content-space-between items-center">
            <div className="flex flex-row flex-1 justify-content-space-between items-center w-full">
              <div className="flex flex-row  gap-1 items-center w-full text-nowrap">
                <span className="icon icon-size-20 calibrating-icon"></span>
                <SubactionHeader
                  className="text-white calibration-header-shimmer text-nowrap"
                  text={calibrationMessages[messageIndex]}
                />
              </div>

              <div className="flex flex-row flex-1 items-center">
                <span className="text md text-gray p-1">
                  {recordingProgress.toFixed(0)}%
                </span>
                <IconButton
                  icon="explainer-icon"
                  className="button sm"
                  onClick={() => {}} // shows onboarding tooltips
                  tooltip
                  tooltipText="How to calibrate"
                  tooltipPosition="pos-left"
                />
              </div>
            </div>
            <div className="calibration-progress-columns w-full overflow-hidden br-1 flex items-end">
              {Array.from({ length: 26 }).map((_, index) => {
                const isActive = (index / 26) * 100 <= recordingProgress;
                return (
                  <div key={index} className={isActive ? "is-active" : ""} />
                );
              })}
            </div>
          </div>
        </div>
        <div className="charuco-settings-action-container while-recording flex flex-row items-center gap-1">
          {charucoTags.map((tag) => (
            <span
              key={tag}
              className="text-gray tag text-nowrap text md text-align-left"
            >
              {tag}
            </span>
          ))}
        </div>
        <div className="stop-calibration flex flex-row flex-1 justify-content-space-between items-center w-full">
          <ButtonSm
            iconClass=""
            text="Stop Recording & Calibrate"
            className="accent button min-w-full full-width-text-center"
            onClick={dispatchStopCalibrationRecording}
            tooltip={true}
            tooltipText="Stop Recording & Calibrate"
            tooltipPosition="pos-top"
          />
        </div>
      </div>
    );
  }

  // Calibrated
  if (isCalibrated) {
    return (
      <div
        className="calibration-module-calibarted z-4 flex flex-col p-1 bg-middark br-1 pos-rel"
        style={{ minWidth: 0 }}
      >
        {errorBanner}
        <div className="flex flex-row items-center">
          <div
            className="flex flex-row flex-1 justify-content-space-between items-center w-full"
            style={{ minWidth: 0 }}
          >
            <div
              className="flex flex-row items-center flex-1"
              style={{ minWidth: 0 }}
            >
              <div className="calibrate-icon-group flex flex-row items-center">
                <span className="icon calibrated-icon icon-size-20" />
                <p className="text md text-success p-1">Calibrated</p>
              </div>
              <div
                className="recording-path-preview tooltip-wrapper pos-rel flex flex-row items-center flex-1 p-1"
                style={{ minWidth: 0, overflow: "visible" }}
              >
                <div className="recording-path-part">
                  <p className="text-gray text md">{calibrationPathDir}</p>
                </div>
                <p
                  className="text-gray text md text-nowrap text-align-left"
                  style={{ flexShrink: 0 }}
                >
                  {calibrationPathFilename}
                </p>
                {loadedCalibration?.path && (
                  <div
                    className="tooltip-container elevated-sharp pos-bottom p-01 br-2 bg-dark"
                    style={{ minWidth: "auto", width: 270, maxWidth: "90vw" }}
                  >
                    <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
                      <p
                        className="text-white text md"
                        style={{
                          fontFamily: "monospace",
                          whiteSpace: "normal",
                          wordBreak: "break-all",
                        }}
                      >
                        {loadedCalibration.path}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="flex flex-row gap-1 items-center">
              <IconButton
                icon="explainer-icon"
                className="button sm"
                onClick={() => {}} // shows onboarding tooltips
                tooltip
                tooltipText="How to calibrate"
                tooltipPosition="pos-left"
              />
            </div>
          </div>
        </div>
        <div className="groupe-2-action- flex flex-row pos-rel justify-content-space-between items-center gap-1">
          <div className="flex flex-row items-center how-it-was-made-group">
            <div className="how-it-was-made-inner-group pos-rel flex flex-row items-center">
              <span
                className={`icon ${SOURCE_ICONS[calibrationSource]} icon-size-20`}
              />
              <span className="icon snaptogrid-icon icon-size-20" />
            </div>
            <div className="charuco-group-on-it-was-adhjusted- charuco-settings-action-container flex flex-row items-center gap-1">
              {charucoTags.map((tag) => (
                <span
                  key={tag}
                  className="text-gray tag text-nowrap text md text-align-left"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <IconButton
            icon="cancelcalibrate-icon"
            className="button sm"
            onClick={handleClearCalibration}
            tooltip
            tooltipText="Clear calibration"
            tooltipPosition="pos-left"
          />
        </div>
      </div>
    );
  }

  // Not calibrated, not recording
  return (
    <div className="calibration-module-idle flex flex-col p-1 bg-middark br-1 pos-rel order-2 ">
      {errorBanner}
      <div className="flex flex-row items-center">
        <div className="flex flex-row flex-1 justify-content-space-between items-center w-100">
          <SubactionHeader text="Calibration" />
          <div className="flex flex-row gap-1 items-center">
            <IconButton
              icon="explainer-icon"
              className="button sm"
              onClick={() => {}} // shows onboarding tooltips
              tooltip
              tooltipText="How to calibrate"
              tooltipPosition="pos-left"
            />
          </div>
        </div>
      </div>
      <div
        className="button sm trigger-charuco-settings-flyout flex-wrap flex pos-rel p-1 br-1 flex-row items-center justify-content-space-between"
        onClick={handleToggleSettings}
      >
        <div className="group-1 flex flex-col items-start">
          <p className="text-gray text-nowrap text md text-align-left">
            Charuco board
          </p>
        </div>
        <div className="group-2 flex flex-row pos-rel items-center gap-1">
          <div className="group-2.1 charuco-settings-action-container flex flex-row items-center gap-1">
            {charucoTags.map((tag) => (
              <span
                key={tag}
                className="text-gray tag text-nowrap text md text-align-left"
              >
                {tag}
              </span>
            ))}
          </div>
          <div className="group-2.2 pos-rel flex flex-col items-center">
            <span className="icon settings-icon icon-size-20" />
          </div>
        </div>
      </div>
      {showCalibrationSettings && (
        <CalibrationSettings onClose={handleCloseSettings} />
      )}
      <div className="p-1 group-3 calibration-action-container flex flex-row items-center">
        {/* 
          The calibration dropdown is always visible.
          However, the "Record and Calibrate" option inside it is hidden in playback mode.
        */}
        <DropdownButton
          buttonProps={{
            text: "Calibrate",
            iconClass: "calibrate-icon",
            className: "button sm min-w-full justify-center",
            buttonType: "secondary",
            textClass: "text-center text bg",
          }}
          dropdownItems={dropdownItems}
          dropdownClassName=""
        />
      </div>
      <ToggleComponent
        text="Align to initial Charuco ground plane"
        iconClass="snaptogrid-icon"
        isToggled={config.useGroundplane}
        onToggle={(checked) =>
          updateCalibrationConfig({ useGroundplane: checked })
        }
        disabled={isLoading}
      />
    </div>
  );
};

export default CalibrationModule;
