import React, { useEffect, useRef, useState } from "react";
import {
  baseNameChanged,
  createSubfolderToggled,
  currentIncrementChanged,
  customSubfolderNameChanged,
  recordingInfoUpdated,
  recordingTagChanged,
  useIncrementToggled,
  useTimestampToggled,
} from "@/store/slices/recording/recording-slice";
import { useAppDispatch, useAppSelector } from "@/store";
import { getTimestampString } from "@/components/control-panels/recording-info-panel/getTimestampString";
import { RecordingPathModal } from "./RecordingPathModal";
import TextSelector from "@/components/ui-components/TextSelector";
import IconButton from "@/components/ui-components/IconButton";
import { useTranslation } from "react-i18next";
import { useElectronIPC } from "@/services/electron-ipc/electron-ipc";

export const RecordingPathPanel: React.FC = () => {
  const dispatch = useAppDispatch();
  const recordingInfo = useAppSelector((state) => state.recording);
  const {
    createSubfolder,
    useTimestamp,
    useIncrement,
    currentIncrement,
    baseName,
    customSubfolderName,
    recordingTag,
  } = recordingInfo.config;

  const [pathModalOpen, setPathModalOpen] = useState(false);
  const [tagInputVisible, setTagInputVisible] = useState(false);
  const tagInputContainerRef = useRef<HTMLDivElement>(null);
  const [previewTimestamp, setPreviewTimestamp] = useState(() =>
    getTimestampString(),
  );

  const { isElectron, api } = useElectronIPC();
  const { t } = useTranslation();

  useEffect(() => {
    if (recordingInfo.isRecording) return;
    const id = setInterval(
      () => setPreviewTimestamp(getTimestampString()),
      1000,
    );
    return () => clearInterval(id);
  }, [recordingInfo.isRecording]);

  useEffect(() => {
    setTagInputVisible(!!recordingTag);
  }, [recordingTag]);

  // Build display path for the read-only preview
  const previewNameParts = useTimestamp ? [previewTimestamp] : [baseName];
  if (recordingTag) previewNameParts.push(recordingTag);
  if (useIncrement) previewNameParts.push(String(currentIncrement));
  const previewName = previewNameParts.join("_");
  const displayPath =
    createSubfolder && customSubfolderName
      ? `${recordingInfo.recordingDirectory}/${customSubfolderName}/${previewName}`
      : `${recordingInfo.recordingDirectory}/${previewName}`;

  const modalProps = {
    recordingDirectory: recordingInfo.recordingDirectory,
    countdown: null,
    recordingTag,
    useTimestamp,
    baseName,
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
    <div className="file-directory-group bg-middark br-2 p-1 flex flex-col gap-1 br-1">
      <div className="file-directory-group justify-content-space-between flex flex-row items-center">
        <p className="text-nowrap text-left bg-md text-darkgray p-1">
          Set folder directory
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
              setTimeout(() => {
                const btn = tagInputContainerRef.current?.querySelector("button");
                btn?.click();
              }, 0);
            } else {
              dispatch(recordingTagChanged(""));
            }
          }}
        />
      </div>
      {/* Read-only path preview */}
      <div className="file-directory-group justify-content-space-between flex flex-row items-center w-full">
        <button
          className="button-sm-group gap-1 br-1 w-full min-w-full justify-content-space-between button items-center sm fit-content flex-inline text-left items-center text-black "
          onClick={() => setPathModalOpen(true)}
        >
          <div  className="gap-1 br-1 flex-1 min-w-0 items-center sm fit-content p-0 flex-inline text-left items-center text-black "
>
            <span className="icon icon-size-20 subfolder-icon" />
            <p className="text-gray text-nowrap text md text-align-left flex flex-end">
              {displayPath || "Set recording path"}
            </p>
          </div>
          <span className="icon icon-size-20 settings-icon"></span>
        </button>
        
      </div>

      {/* Tag input */}
      <div ref={tagInputContainerRef}>
        {tagInputVisible && (
          <div className="flex flex-row gap-1 p-2 items-center">
            <span className="icon icon-size-20 subcat-icon"></span>
            <TextSelector
              value={recordingTag}
              onChange={(v) => dispatch(recordingTagChanged(v))}
              placeholder={t("recordingTagPlaceholder")}
            />
          </div>
        )}
      </div>

      <RecordingPathModal
        open={pathModalOpen}
        onClose={() => setPathModalOpen(false)}
        {...modalProps}
      />
    </div>
  );
};