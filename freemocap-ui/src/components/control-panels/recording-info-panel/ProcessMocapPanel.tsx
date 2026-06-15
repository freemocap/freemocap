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
        </div>
      </div>

      {/* Mocap Setup Modal */}
      {mocapSetupModalOpen && (
        <MocapSetupModal onClose={() => setMocapSetupModalOpen(false)} />
      )}
    </>
  );
};
