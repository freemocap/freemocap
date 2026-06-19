import React, { useEffect, useState } from "react";
import {
  recordingInfoUpdated,
  startRecording,
  stopRecording,
  useAppDispatch,
  useAppSelector,
} from "@/store";
import {
  autoProcessToggled,
  baseNameChanged,
  countdownSet,
  createSubfolderToggled,
  currentIncrementChanged,
  currentIncrementIncremented,
  customSubfolderNameChanged,
  delaySecondsChanged,
  micDeviceIndexChanged,
  pendingOperationSet,
  recordingTagChanged,
  recordingTypePresetChanged,
  useDelayStartToggled,
  useIncrementToggled,
  useTimestampToggled,
} from "@/store/slices/recording/recording-slice";
import type { RecordingTypePreset } from "@/store/slices/recording/recording-types";
import { calibrateRecording } from "@/store/slices/calibration/calibration-thunks";
import { processMocapRecording } from "@/store/slices/mocap/mocap-thunks";
import { PresetPicker } from "@/components/common/PresetPicker";
import { DelayRecordingStartControl } from "./recording-subcomponents/DelayRecordingStartControl";
import { MicrophoneSelector } from "@/components/control-panels/recording-info-panel/recording-subcomponents/MicrophoneSelector";
import { useElectronIPC } from "@/services/electron-ipc/electron-ipc";
import { useServer } from "@/services/server/ServerContextProvider";
import { getTimestampString } from "@/store/slices/recording/getTimestampString";
import { StartStopRecordingButton } from "./recording-subcomponents/StartStopRecordingButton";
import { RecordingPathModal } from "./RecordingPathModal";
import TextSelector from "@/components/ui-components/TextSelector";
import { useTranslation } from "react-i18next";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import MocapSetupModal from "@/components/mocap-setup/mocap-setup-modal";
import IconButton from "@/components/ui-components/IconButton";
import { useRef } from "react";

export type { RecordingTypePreset };

export const RECORDING_TYPE_OPTIONS: {
  value: RecordingTypePreset;
  label: string;
}[] = [
  { value: "none", label: "None" },
  { value: "calibration", label: "Calibration" },
  { value: "mocap", label: "Mocap" },
];

export const RecordingInfoPanel: React.FC = () => {
  const dispatch = useAppDispatch();
  const recordingInfo = useAppSelector((state) => state.recording);
  const { config, pendingOperation, countdown } = recordingInfo;
  const {
    createSubfolder,
    useDelayStart,
    delaySeconds,
    useTimestamp,
    useIncrement,
    currentIncrement,
    baseName,
    customSubfolderName,
    recordingTag,
    micDeviceIndex,
    recordingTypePreset,
    autoProcess,
  } = config;

  const [pathModalOpen, setPathModalOpen] = useState(false);
  const [mocapSetupModalOpen, setMocapSetupModalOpen] = useState(false);
  const [tagInputVisible, setTagInputVisible] = useState(false);
  const tagInputContainerRef = useRef<HTMLDivElement>(null);
  const [previewTimestamp, setPreviewTimestamp] = useState(() =>
    getTimestampString(),
  );

  const { isElectron, api } = useElectronIPC();
  const { connectedCameraIds } = useServer();
  const { t } = useTranslation();
  const noCamerasConnected = connectedCameraIds.length === 0;

  useEffect(() => {
    if (recordingInfo.isRecording) return;
    const id = setInterval(
      () => setPreviewTimestamp(getTimestampString()),
      1000,
    );
    return () => clearInterval(id);
  }, [recordingInfo.isRecording]);

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
    if (
      recordingInfo?.recordingDirectory?.startsWith("~") &&
      isElectron &&
      api
    ) {
      api.fileSystem.getHomeDirectory
        .query()
        .then((homePath: string) => {
          const updatedDirectory = recordingInfo.recordingDirectory
            .replace("~", homePath)
            .replace(/\\/g, "/");
          dispatch(
            recordingInfoUpdated({ recordingDirectory: updatedDirectory }),
          );
        })
        .catch((error: unknown) => {
          console.error("Failed to get home directory:", error);
          throw error;
        });
    }
  }, [recordingInfo.recordingDirectory, isElectron, api, dispatch]);

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
    const nameParts = useTimestamp ? [ts] : [baseName];
    if (recordingTypePreset !== "none") nameParts.push(recordingTypePreset);
    if (recordingTag) nameParts.push(recordingTag);
    const recordingName = nameParts.join("_");
    const subfolderName = createSubfolder
      ? customSubfolderName || getTimestampString()
      : "";
    const recordingPath = createSubfolder
      ? recordingInfo.recordingDirectory + "/" + subfolderName
      : recordingInfo.recordingDirectory;

    if (useIncrement) dispatch(currentIncrementIncremented());
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

  // Build display path for the read-only preview
  const previewNameParts = useTimestamp ? [previewTimestamp] : [baseName];
  if (recordingTypePreset !== "none")
    previewNameParts.push(recordingTypePreset);
  if (recordingTag) previewNameParts.push(recordingTag);
  if (useIncrement) previewNameParts.push(String(currentIncrement));
  const previewName = previewNameParts.join("_");
  const displayPath =
    createSubfolder && customSubfolderName
      ? `${recordingInfo.recordingDirectory}/${customSubfolderName}/${previewName}`
      : `${recordingInfo.recordingDirectory}/${previewName}`;

  const recordingStartTime = recordingInfo.startedAt
    ? new Date(recordingInfo.startedAt).getTime()
    : null;

  const handleToggleSettings = () => {
    setMocapSetupModalOpen(true);
  };

  const modalProps = {
    recordingDirectory: recordingInfo.recordingDirectory,
    countdown,
    recordingTag,
    useTimestamp,
    baseName,
    recordingTypePreset,
    useIncrement,
    currentIncrement,
    createSubfolder,
    customSubfolderName,
    isRecording: recordingInfo.isRecording,
    onTagChange: (v: string) => dispatch(recordingTagChanged(v)),
    onNameChange: (v: string) => {
      dispatch(useTimestampToggled(false));
      dispatch(baseNameChanged(v));
    },
    onUseTimestampChange: (v: boolean) => dispatch(useTimestampToggled(v)),
    onBaseNameChange: (v: string) => dispatch(baseNameChanged(v)),
    onUseIncrementChange: (v: boolean) => dispatch(useIncrementToggled(v)),
    onIncrementChange: (v: number) => dispatch(currentIncrementChanged(v)),
    onCreateSubfolderChange: (v: boolean) =>
      dispatch(createSubfolderToggled(v)),
    onCustomSubfolderNameChange: (v: string) =>
      dispatch(customSubfolderNameChanged(v)),
  };

  return (
    <>
      <div className="main-side-actions flex flex-col gap-1 order-3">
        {/* File directory group */}
        <div className="file-directory-group bg-middark br-2 p-1 flex flex-col gap-1 br-1 ">
        <div className="file-directory-group justify-content-space-between flex flex-row">
            <p className="text-nowrap text-left bg-md text-darkgray p-1">
              File directory
            </p>
            <IconButton
            icon={tagInputVisible ? "tag-active-icon" : "tag-icon"}
            tooltip={true}
            tooltipPosition="pos-left"
            tooltipText={tagInputVisible ? "Remove tag" : "Add tag"}
            className={`icon-size-25 ${tagInputVisible ? "activate" : ""}`}
            onClick={() => {
              const newState = !tagInputVisible;
              setTagInputVisible(newState);
              if (newState) {
                // Simulate click on the TextSelector button after render
                setTimeout(() => {
                  const btn = tagInputContainerRef.current?.querySelector("button");
                  btn?.click();
                }, 0);
              }
            }}
            />
          </div>
          {/* Read-only path preview */}
          <button
            className="button-sm-group gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black full-width w-full"
            onClick={() => setPathModalOpen(true)}
          >
            <span className="icon icon-size-20 subfolder-icon" />
            <p className="text-gray text-nowrap text md text-align-left flex flex-end">
              {displayPath || "Set recording path"}
            </p>
          </button>

          {/* Tag input */}
          <div ref={tagInputContainerRef}>
            {tagInputVisible && (
              <TextSelector
                value={recordingTag}
                onChange={(v) => dispatch(recordingTagChanged(v))}
                placeholder={t("recordingTagPlaceholder")}
              />
            )}
          </div>

          <RecordingPathModal
            open={pathModalOpen}
            onClose={() => setPathModalOpen(false)}
            {...modalProps}
          />
        </div>

        {/* Record group */}
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
              {/* put the delay toggle below here  */}
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