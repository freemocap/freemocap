import React, { useState } from "react";
import ButtonSm from "@/components/ui-components/ButtonSm";
import SubactionHeader from '@/components/ui-components/SubactionHeader';

import MOCAPthreeDReconstructionSettings from "@/components/mocap-setup/mocap-3dreconstruction-settings";
import MOCAPMediaPipeDetectorSettings from "@/components/mocap-setup/mocap-mediapipedetector-settings";
import MOCAPBlenderSettings from "@/components/mocap-setup/mocap-blender-settings";

interface MocapSetupModalProps {
  onClose?: () => void;
}

const MocapSetupModal: React.FC<MocapSetupModalProps> = ({ onClose }) => {
  const [activeButton, setActiveButton] = useState<"button1" | "button2" | "button3">("button1");

  const renderRightPanelContent = () => {
    switch (activeButton) {
      case "button1":
        try {
          return <MOCAPthreeDReconstructionSettings open={true} onClose={() => {}} />;
        } catch (error) {
          console.error("Error rendering 3D Reconstruction Settings:", error);
          return (
            <div className="flex flex-col gap-2 p-2 bg-dark br-2">
              <p className="text-white text md">3D Reconstruction Settings</p>
              <p className="text-gray text sm">Failed to load component. Check if the export is correct.</p>
            </div>
          );
        }
      case "button2":
        try {
          return <MOCAPMediaPipeDetectorSettings open={true} onClose={() => {}} />;
        } catch (error) {
          console.error("Error rendering MediaPipe Detector Settings:", error);
          return (
            <div className="flex flex-col gap-2 p-2 bg-dark br-2">
              <p className="text-white text md">MediaPipe Detector Settings</p>
              <p className="text-gray text sm">Failed to load component. Check if the export is correct.</p>
            </div>
          );
        }
      case "button3":
        try {
          return <MOCAPBlenderSettings open={true} onClose={() => {}} />;
        } catch (error) {
          console.error("Error rendering Blender Settings:", error);
          return (
            <div className="flex flex-col gap-2 p-2 bg-dark br-2">
              <p className="text-white text md">Blender Settings</p>
              <p className="text-gray text sm">Failed to load component. Check if the export is correct.</p>
            </div>
          );
        }
      default:
        return null;
    }
  };

  return (
    <>
      {/* Backdrop overlay */}
      <div 
        className="pos-fixed inset-0 bg-surface-overlay z-10" 
       
        onClick={onClose}
      />
      
      {/* Modal */}
      <div 
        className="mocap-settings-modal overflow-hidden pos-fixed elevated-sharp p-1 b-2 flex flex-col br-2" 

      >
        {/* <div className="flex items-center justify-content-space-between p-3 border-1 border-bottom" style={{ borderColor: "var(--color-border-secondary)" }}>
          <h3 className="text-white text lg">Mocap Setup</h3>
          <ButtonSm text="Close" iconClass="clear-icon" buttonType="secondary" onClick={onClose} />
        </div> */}

        {/* Row 1 */}
        <div className="inner-container-settings- flex flex-row flex-1 h-inherit br-2">
          {/* Column 1 - Buttons */}
            

          <div className="left-section-actions br-1 p-2 bg-tertiary flex flex-col flex-1 gap-2" style={{ maxWidth: 146, flexShrink: 0 }}>
            <SubactionHeader 
            text="Mocap setup" 
            className="text-gray"/>
            <ButtonSm
              text="3D Reconstruction"
              buttonType={activeButton === "button1" ? "activated" : "idle"}
              className="full-width quaternary"
              onClick={() => setActiveButton("button1")}
            />
            <ButtonSm
              text="MediaPipe Detector"
              buttonType={activeButton === "button2" ? "activated" : "idle"}
              className="full-width quaternary"
              onClick={() => setActiveButton("button2")}
            />
            <ButtonSm
              text="Blender"
              buttonType={activeButton === "button3" ? "activated" : "idle"}
              className="full-width quaternary"
              onClick={() => setActiveButton("button3")}
            />
          </div>
          
          {/* Column 2 - Dynamic Content */}
          <div className="right-side-settings-container overflow-y p-2 flex-1 flex w-full flex-row">
            {renderRightPanelContent()}
          </div>
        </div>

        {/* Row 2 */}
        <div className="bottom-area-action-container flex flex-col align-end bottom-row gap-2 p-2 pt-0">
          {/* Column 1 - Two buttons */}
          <div className="flex flex-row gap-2 h-full">
            <ButtonSm
              text="Close"
              buttonType="quaternary"
              className=""
              onClick={onClose}
            />
            <ButtonSm
              text="Process Mocap"
              textColor="text-white"
              iconClass="processmocap-icon"
              buttonType=""
              className="primary accent"
              onClick={() => {}}
              tooltip={true}
              tooltipPosition="pos-top"
              tooltipText="Start mocap processing"
            />
          </div>
          <div className="flex flex-row gap-2 h-full">
            <p className="text sm text-gray">Processing may take hours, depending on your system, ideally avoid using your computer.</p></div>
          </div>
      </div>
    </>
  );
};

export default MocapSetupModal;