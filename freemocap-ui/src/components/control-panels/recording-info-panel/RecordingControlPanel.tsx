import React, { useEffect, useState } from "react";
import {
  autoProcessToggled,
  countdownSet,
  delaySecondsChanged,
  micDeviceIndexChanged,
  pendingOperationSet,
  recordingTypePresetChanged,
  useDelayStartToggled,
} from "@/store/slices/recording/recording-slice";
import type { RecordingTypePreset } from "@/store/slices/recording/recording-types";
import { useAppDispatch, useAppSelector } from "@/store";
import { startRecording, stopRecording } from "@/store";
import { calibrateRecording } from "@/store/slices/calibration/calibration-thunks";
import { processMocapRecording } from "@/store/slices/mocap/mocap-thunks";
import { PresetPicker } from "@/components/common/PresetPicker";
import { DelayRecordingStartControl } from "./recording-subcomponents/DelayRecordingStartControl";
import { MicrophoneSelector } from "@/components/control-panels/recording-info-panel/recording-subcomponents/MicrophoneSelector";
import { useServer } from "@/services/server/ServerContextProvider";
import { getTimestampString } from "@/components/control-panels/recording-info-panel/getTimestampString";
import { StartStopRecordingButton } from "./recording-subcomponents/StartStopRecordingButton";
import { useTranslation } from "react-i18next";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import MocapSetupModal from "@/components/mocap-setup/mocap-setup-modal";

export const RECORDING_TYPE_OPTIONS: {
  value: RecordingTypePreset;
  label: string;
}[] = [
  { value: "none", label: "None" },
  { value: "calibration", label: "Calibration" },
  { value: "mocap", label: "Mocap" },
];

export const RecordingControlPanel: React.FC = () => {
  const dispatch = useAppDispatch();
  const recordingInfo = useAppSelector((state) => state.recording);
  const { config, pendingOperation, countdown } = recordingInfo;
  const {
    useDelayStart,
    delaySeconds,
    micDeviceIndex,
    recordingTypePreset,
    autoProcess,
  } = config;

  const [mocapSetupModalOpen, setMocapSetupModalOpen] = useState(false);

  const { connectedCameraIds } = useServer();
  const { t } = useTranslation();
  const noCamerasConnected = connectedCameraIds.length === 0;

  useEffect(() => {
    if (!pendingOperation) return;
    const timeoutMs = 5000;
    const elapsed = Date.now() - pendingOperation.timestamp;
    const remaining = Math.max(0, timeoutMs - elapsed);
    const timer = setTimeout(() => {
      console.error(
        "Recording " +
          pendingOperation.type +
          " operation timed out after " +
          timeoutMs +
          "ms",
      );
      dispatch(pendingOperationSet(null));
    }, remaining);
    return () => clearTimeout(timer);
  }, [dispatch, pendingOperation]);

  useEffect(() => {
    if (countdown === null) return;
    if (countdown > 0) {
      const timer = setTimeout(
        () => dispatch(countdownSet(countdown - 1)),
        1000,
      );
      return () => clearTimeout(timer);
    }
    dispatch(countdownSet(null));
    handleStartRecording();
  }, [countdown]);

  const handleStartRecording = async (): Promise<void> => {
    const ts = getTimestampString();
    const nameParts = config.useTimestamp ? [ts] : [config.baseName];
    if (recordingTypePreset !== "none") nameParts.push(recordingTypePreset);
    if (config.recordingTag) nameParts.push(config.recordingTag);
    const recordingName = nameParts.join("_");
    const subfolderName = config.createSubfolder
      ? config.customSubfolderName || getTimestampString()
      : "";
    const recordingPath = config.createSubfolder
      ? recordingInfo.recordingDirectory + "/" + subfolderName
      : recordingInfo.recordingDirectory;

    if (config.useIncrement) {
      // Import dynamically to avoid cycle
      const { currentIncrementIncremented } = await import("@/store/slices/recording/recording-slice");
      dispatch(currentIncrementIncremented());
    }
    dispatch(pendingOperationSet({ type: "start", timestamp: Date.now() }));

    try {
      await dispatch(
        startRecording({
          recordingName,
          recordingDirectory: recordingPath,
          micDeviceIndex,
        }),
      ).unwrap();
    } catch (error) {
      console.error("Failed to start recording:", error);
      dispatch(pendingOperationSet(null));
      throw error;
    }
  };

  const handleRecordButtonClick = async (): Promise<void> => {
    if (pendingOperation) return;

    if (recordingInfo.isRecording) {
      dispatch(pendingOperationSet({ type: "stop", timestamp: Date.now() }));
      try {
        const result = await dispatch(stopRecording()).unwrap();
        if (result && autoProcess && recordingTypePreset === "calibration") {
          dispatch(calibrateRecording());
        } else if (result && autoProcess && recordingTypePreset === "mocap") {
          dispatch(processMocapRecording());
        }
      } catch (error) {
        console.error("Failed to stop recording:", error);
        dispatch(pendingOperationSet(null));
        throw error;
      }
    } else if (countdown !== null) {
      // Cancel the countdown and return to idle state
      dispatch(countdownSet(null));
    } else if (useDelayStart) {
      dispatch(countdownSet(delaySeconds));
    } else {
      await handleStartRecording();
    }
  };

  const recordingStartTime = recordingInfo.startedAt
    ? new Date(recordingInfo.startedAt).getTime()
    : null;

  const handleToggleSettings = () => {
    setMocapSetupModalOpen(true);
  };

  return (
    <>
      <div className="record-group bg-middark br-2 p-1 flex flex-col gap-1 br-1 p-2 pb-2 order-4">
        <div
          className="flex flex-row flex-1 items-center gap-1 w-full"
          onClick={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <StartStopRecordingButton
            isRecording={recordingInfo.isRecording}
            isPending={pendingOperation !== null}
            countdown={countdown}
            recordingStartTime={recordingStartTime}
            disabled={noCamerasConnected && !recordingInfo.isRecording}
            tooltipText={
              noCamerasConnected && !recordingInfo.isRecording
                ? t("connectCamerasToRecord")
                : undefined
            }
            onClick={handleRecordButtonClick}
          />
        </div>
        {/* Delay toggle */}
        <DelayRecordingStartControl
          useDelay={useDelayStart}
          delaySeconds={delaySeconds}
          onDelayToggle={(v) => dispatch(useDelayStartToggled(v))}
          onDelayChange={(v) => dispatch(delaySecondsChanged(v))}
        />
        {/* Preset + auto-process */}
        <div className="flex flex-start flex-col items-center gap-1">
          <PresetPicker
            value={recordingTypePreset}
            options={RECORDING_TYPE_OPTIONS}
            onChange={(v) => dispatch(recordingTypePresetChanged(v))}
            disabled={recordingInfo.isRecording}
          />
          <ToggleComponent
            text="Auto Process Mocap"
            isToggled={autoProcess}
            onToggle={(v) => dispatch(autoProcessToggled(v))}
            disabled={
              recordingTypePreset === "none" || recordingInfo.isRecording
            }
          />
        </div>
        <div
          className={
            "streaming-mode mocap-settings-button " +
            (autoProcess &&
            recordingTypePreset !== "none" &&
            !recordingInfo.isRecording
              ? ""
              : "disabled ") +
            "button sm flex-wrap flex pos-rel p-1 br-1 flex-row items-center justify-content-space-between"
          }
          onClick={handleToggleSettings}
        >
          <div className=" flex flex-row items-start items-center gap-1">
            <span className="icon subcat-icon icon-size-20" />
            <p className="text-gray text-nowrap text md text-align-left">
              Mocap Settings
            </p>
          </div>
          <div className="group-2 flex flex-row pos-rel items-center gap-1">
            <div className="group-2.2 pos-rel flex flex-col items-center">
              <span className="icon settings-icon icon-size-20" />
            </div>
          </div>
        </div>

        <MicrophoneSelector
          selectedMicIndex={micDeviceIndex}
          onMicSelected={(idx) => dispatch(micDeviceIndexChanged(idx))}
          disabled={recordingInfo.isRecording}
        />
      </div>

      {/* Mocap Setup Modal */}
      {mocapSetupModalOpen && (
        <MocapSetupModal
          mode="recording"
          onClose={() => setMocapSetupModalOpen(false)}
        />
      )}
    </>
  );
};