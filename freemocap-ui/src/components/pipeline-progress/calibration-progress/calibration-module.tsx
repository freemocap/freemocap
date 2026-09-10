import AnchoredInfo from '@/components/ui-components/AnchoredInfo';
import {CalibrationBoardMode} from "@/store/slices/calibration/calibration-types";
import React, { useCallback, useMemo, useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import IconButton from "@/components/ui-components/IconButton";
import DropdownButton from "@/components/ui-components/DropdownButton";
import CalibrationSettings from "./calibration-settings";
import {useCalibrationTomlLoader} from '@/components/viewport3d/hooks/useCalibrationTomlLoader';
// import CalibrationReferenceFrame from './calibration-reference-frame';
import ButtonSm from "@/components/ui-components/ButtonSm";
import ImportVideosModal from "@/components/control-panels/mocap-control-panel/ImportVideosModal";
import charucoBoardImage from "@/assets/images/charuco_board.webp";
import { useCalibration } from "@/hooks/useCalibration";
import { useElectronIPC, useServer } from "@/services";
import { useAppDispatch, useAppSelector } from "@/store";
import {
  calibrationAutoLoadDismissed,
  calibrationLoadedFromBundle,
  loadCalibrationToml,
  loadMostRecentCalibration,
  selectLoadedCalibration,
} from "@/store/slices/calibration";
import { selectIsLoading } from "@/store/slices/cameras/cameras-selectors";
import { getTimestampString } from "@/store/slices/recording/getTimestampString";
import "@/styles/calibration.css";


type CalibrationSource = "record" | "import-videos" | "import-toml";
type AppMode = "streaming" | "playback";

const SOURCE_ICONS: Record<CalibrationSource, string> = {
  record: "record-icon",
  "import-videos": "importVideos-icon",
  "import-toml": "tomlfile-icon",
};

interface CalibrationModuleProps {
  isCalibrated?: boolean;
  /**
   * Optionally override the app mode detection.
   * When provided, this takes precedence over route-based mode detection.
   */
  appModeOverride?: "streaming" | "playback";
}

const CalibrationModule = ({
  isCalibrated: isCalibratedProp,
  appModeOverride,
}: CalibrationModuleProps) => {
  const dispatch = useAppDispatch();
  const { api, isElectron } = useElectronIPC();
  const { connectedCameraIds, isConnected, isFailed } = useServer();
  const loadedCalibration = useAppSelector(selectLoadedCalibration);
  const isCamerasLoading = useAppSelector(selectIsLoading);

  const {
    config,
    error,
    isLoading,
    isRecording,
    recordingProgress,
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
  const [isStopping, setIsStopping] = useState(false);
  const [recordingStartTime, setRecordingStartTime] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [showImportVideosModal, setShowImportVideosModal] = useState(false);

  const location = useLocation();
  const appMode: AppMode = appModeOverride ?? (location.pathname === "/playback" ? "playback" : "streaming");
  useCalibrationTomlLoader(appMode === 'streaming' && appModeOverride === undefined);
  // TODO: Revisit reference-frame controls once the core workflow is stable.
  // const referenceFrameControls = appMode === 'streaming' && appModeOverride === undefined
  //   ? <CalibrationReferenceFrame calibrationPath={loadedCalibration?.path ?? null}/>
  //   : null;
  const panelTitle = appModeOverride === undefined ? 'Capture volume' : 'Calibration';

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
      setIsStopping(false); // Reset stopping state when recording stops
      setRecordingStartTime(null);
      return;
    }
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % calibrationMessages.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [isRecording, calibrationMessages.length]);

  // Track recording start time for timestamp
  useEffect(() => {
    if (isRecording && !recordingStartTime) {
      setRecordingStartTime(Date.now());
      setElapsedSeconds(0);
    }
    if (!isRecording) {
      setRecordingStartTime(null);
      setElapsedSeconds(0);
    }
  }, [isRecording]);

  // Update elapsed time every second during recording
  useEffect(() => {
    if (!isRecording) return;
    
    const interval = setInterval(() => {
      if (recordingStartTime) {
        const currentElapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
        setElapsedSeconds(currentElapsed);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [isRecording, recordingStartTime]);

  // Format elapsed time as MM:SS
  const formatElapsedTime = (totalSeconds: number): string => {
    const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const seconds = (totalSeconds % 60).toString().padStart(2, '0');
    return `${minutes}:${seconds}`;
  };


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
    config.boardMode === CalibrationBoardMode.AUTO
      ? "AUTO"
      : `${config.charucoBoard.squares_x}x${config.charucoBoard.squares_y}`,
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

  const handleOpenImportVideos = useCallback(() => {
    setShowImportVideosModal(true);
  }, []);

  const handleVideosImported = useCallback(
    async (result: { recordingPath: string }) => {
      setCalibrationSource("import-videos");
      dispatch(calibrationAutoLoadDismissed(null));
      await setManualRecordingPath(result.recordingPath);
      calibrateSelectedRecording();
    },
    [dispatch, setManualRecordingPath, calibrateSelectedRecording],
  );

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
      <ButtonSm
        iconClass="tomlfile-icon"
        text="Load most recent calibration TOML (default)"
        buttonType="secondary"
        className="full-width"
        onClick={() => {void dispatch(loadMostRecentCalibration());}}
        disabled={!isConnected || isLoading}
      />
      {/* 
        "Record and Calibrate" is only available in streaming mode.
        In playback mode, this option is hidden since recording doesn't make sense.
      */}
      {shouldShowRecordAndCalibrate && (
        <ButtonSm
          iconClass="record-icon"
          text="Record calibration videos"
          className="full-width"
          textClass="text-align-left"
          onClick={handleRecordAndCalibrate}
        />
      )}
      <ButtonSm
        iconClass="importVideos-icon"
        text="Import calibration videos"
        className="full-width"
        textClass="text-align-left"
        onClick={handleOpenImportVideos}
        disabled={!isElectron || isLoading}
      />
      <ButtonSm
        iconClass="tomlfile-icon"
        text="Load calibration TOML"
        className="full-width"
        textClass="text-align-left"
        onClick={handleImportToml}
        disabled={!isElectron || isLoading}
      />
    </div>
  );

  const calibrationDropdown = <DropdownButton
    buttonProps={{text: 'Set up calibration', rightSideIcon: 'dropdown', iconClass: 'calibrate-icon',
      className: 'button sm min-w-full justify-center', buttonType: 'secondary'}}
    dropdownItems={dropdownItems}/>;

  const errorBanner = error && (
    <div className="toast-notification gap-4 error flex items-center justify-content-space-between elevated-sharp">
      <p className="text sm">{error}</p>
      <IconButton icon="close-icon" onClick={clearError} />
    </div>
  );

  const calibrationHelp = <AnchoredInfo title="How to calibrate" text="Print a ChArUco board and enter its measured square size. Show it to every camera while recording; move and rotate it through the capture volume."
    imageSrc={charucoBoardImage} link={{label: 'Download ChArUco board', url: 'https://docs.freemocap.org/documentation/multi-camera-calibration.html'}}/>;
  const importVideosModal = (
    <ImportVideosModal
      open={showImportVideosModal}
      onClose={() => setShowImportVideosModal(false)}
      onImported={handleVideosImported}
      defaultNameTag="imported_calibration"
    />
  );

  // Recording in progress
  if (isRecording) {
    return (
      <>
      {importVideosModal}
    
      <div className="calibration-module-recording flex flex-col p-1 bg-middark br-2 pos-rel gap-1 min-w-0 w-full">
        <SubactionHeader text={panelTitle}/>
        {errorBanner}
        <div className="flex flex-row items-center min-w-0 w-full">
          <div className="flex flex-col flex-1 justify-content-space-between items-center min-w-0 w-full">
            <div className="flex flex-row flex-1 justify-content-space-between items-center w-full">
              <div className="flex flex-row  gap-1 items-center min-w-0 w-full text-nowrap">
                <span className="icon icon-size-20 calibrating-icon"></span>
                <SubactionHeader
                  className="text-white calibration-header-shimmer text-nowrap"
                  text={isStopping ? "Stopping..." : calibrationMessages[messageIndex]}
                />
              </div>

              <div className="flex flex-row items-center gap-2">
                {/* TODO: recordingProgress doesn't update during recording, fix and re-enable
                <span className="text md text-gray p-1">
                  {recordingProgress.toFixed(0)}%
                </span>
                */}
                {calibrationHelp}
              </div>
            </div>
            {/* TODO: recordingProgress doesn't update during recording, fix and re-enable
            <div className="calibration-progress-columns w-full overflow-hidden br-1 flex items-end">
              {Array.from({ length: 26 }).map((_, index) => {
                const isActive = (index / 26) * 100 <= recordingProgress;
                return (
                  <div key={index} className={isActive ? "is-active" : ""} />
                );
              })}
            </div>
            */}
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
            text={
              isStopping 
                ? "Stopping..." 
                : recordingStartTime 
                  ? `Stop Recording & Calibrate ${formatElapsedTime(elapsedSeconds)}` 
                  : "Stop Recording & Calibrate"
            }
            className="accent button min-w-full full-width-text-center"
            onClick={() => {
              setIsStopping(true);
              dispatchStopCalibrationRecording();
            }}
            tooltip={true}
            tooltipText="Stop Recording & Calibrate"
            tooltipPosition="pos-top"
          />
        </div>
      </div>
      </>
    );
  }

  // Calibrated
  if (isCalibrated) {
    return (
      <>
      {importVideosModal}
    
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
                <SubactionHeader text={panelTitle}/>
                <p className="text md text-success p-1">Calibrated</p>
              </div>
              <div
                className="recording-path-preview tooltip-wrapper pos-rel flex flex-row items-center flex-1 p-1"
                style={{ minWidth: 0, overflow: "visible" }}
              >
                <div className="recording-path-part" style={{minWidth: 0, maxWidth: "20%"}}>
                  <p className="text-gray text md">{calibrationPathDir}</p>
                </div>
                <p
                  className="text-gray text md text-nowrap text-align-left"
                  style={{ minWidth: 0, display: "flex", flex: 1 }}
                >
                  <span style={{overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0}}>{calibrationPathFilename.slice(0, Math.ceil(calibrationPathFilename.length / 2))}</span><span style={{flexShrink: 0}}>{calibrationPathFilename.slice(Math.ceil(calibrationPathFilename.length / 2))}</span>
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
              {calibrationHelp}
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
        {calibrationDropdown}
        {/* {referenceFrameControls} */}
      </div>
      </>
    );
  }

  // Not calibrated, not recording
  return (
    <>
    {importVideosModal}
    
    <div className="calibration-module-idle  flex flex-col p-1 bg-middark br-2 pos-rel order-2 ">
      {errorBanner}
      <div className="flex flex-row items-center">
        <div className="flex flex-row flex-1 justify-content-space-between items-center w-100">
          <SubactionHeader text={panelTitle} />
          <div data-onboarding="calibration:what-is-calibration" className="flex flex-row pos-rel gap-1 items-center">
            {calibrationHelp}

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
        {calibrationDropdown}
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
      {/* {referenceFrameControls} */}
    </div>
    </>
  );
};

export default CalibrationModule;




