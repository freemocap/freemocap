import React, { useState } from "react";
import { useAppSelector } from "@/store";
import ButtonSm from "@/components/ui-components/ButtonSm";
import MocapSetupModal from "@/components/mocap-setup/mocap-setup-modal";

export const RecordingInfoPanel: React.FC = () => {
  const recordingInfo = useAppSelector((state) => state.recording);

  const [mocapSetupModalOpen, setMocapSetupModalOpen] = useState(false);

  return (
    <>
        <div className="main-side-actions flex flex-col gap-1 order-3">
        {/* Process group */}
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
