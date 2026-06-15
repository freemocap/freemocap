import React, { useState } from "react";
import { useAppDispatch, useAppSelector } from "@/store";
import { recordingTagChanged } from "@/store/slices/recording/recording-slice";
import { RecordingPathModal } from "./RecordingPathModal";
import ButtonSm from "@/components/ui-components/ButtonSm";
import TextSelector from "@/components/ui-components/TextSelector";
import MocapSetupModal from "@/components/mocap-setup/mocap-setup-modal";

export const RecordingInfoPanel: React.FC = () => {
  const dispatch = useAppDispatch();
  const recordingInfo = useAppSelector((state) => state.recording);
  const { config } = recordingInfo;
  const { recordingTag } = config;

  const [pathModalOpen, setPathModalOpen] = useState(false);
  const [mocapSetupModalOpen, setMocapSetupModalOpen] = useState(false);

  return (
    <>
      <div className="main-side-actions flex flex-col gap-1 order-3">
        {/* File directory group */}
        <div className="file-directory-group justify-content-space-between bg-middark br-2 p-1 flex flex-col gap-1 br-1 pb-2">
          <p className="text-nowrap text-left bg-md text-darkgray p-1">
            File directory
          </p>

          {/* Read-only path preview */}
          <div
            className="button-sm-group gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black full-width"
            style={{ pointerEvents: "none" }}
          >
            <span className="icon icon-size-20 subfolder-icon" />
            <p className="text-gray text-nowrap text md text-align-left flex flex-end">
              {recordingInfo.recordingDirectory || "Set recording path"}
            </p>
          </div>

          {/* Tag + options button */}
          <div className="flex flex-row flex-wrap gap-1 items-center">
            <TextSelector
              value={recordingTag}
              onChange={(v) => dispatch(recordingTagChanged(v))}
              placeholder="Recording tag"
            />
            <ButtonSm
              iconClass="settings-icon"
              text="Recording Options"
              textColor="text-gray"
              onClick={() => setPathModalOpen(true)}
            />
          </div>

          <RecordingPathModal
            open={pathModalOpen}
            onClose={() => setPathModalOpen(false)}
            recordingDirectory={recordingInfo.recordingDirectory}
            countdown={null}
            recordingTag={recordingTag}
            useDelayStart={false}
            delaySeconds={0}
            useTimestamp={false}
            baseName=""
            recordingTypePreset="none"
            useIncrement={false}
            currentIncrement={0}
            createSubfolder={false}
            customSubfolderName=""
            isRecording={false}
            onDelayToggle={() => {}}
            onDelayChange={() => {}}
            onTagChange={() => {}}
            onNameChange={() => {}}
            onUseTimestampChange={() => {}}
            onBaseNameChange={() => {}}
            onUseIncrementChange={() => {}}
            onIncrementChange={() => {}}
            onCreateSubfolderChange={() => {}}
            onCustomSubfolderNameChange={() => {}}
          />
        </div>

        {/* Record group - DUMMY */}
        <div className="process-group bg-middark br-2 p-1 flex flex-col gap-1 br-1 p-2 pb-2 order-4">
          <div className="flex flex-row flex-1 items-center gap-1 w-full">
            <ButtonSm
              text="Continue to Mocap Setup"
              iconClass="processmocap-icon"
              className="accent text-nowrap flex flex-row flex-1 gap-1 br-1 button sm flex-inline text-left items-center full-width primary justify-center"
              onClick={() => setMocapSetupModalOpen(true)}
            />
          </div>

          <div
            className="streaming-mode mocap-settings-button button sm flex-wrap flex pos-rel p-1 br-1 flex-row items-center justify-content-space-between"
            onClick={() => setMocapSetupModalOpen(true)}
          >
            <div className="flex flex-row items-start items-center gap-1">
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
        </div>
      </div>

      {/* Mocap Setup Modal */}
      {mocapSetupModalOpen && (
        <MocapSetupModal onClose={() => setMocapSetupModalOpen(false)} />
      )}
    </>
  );
};
