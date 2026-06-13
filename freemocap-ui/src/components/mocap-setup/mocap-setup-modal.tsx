import React, { useState } from "react";
import ButtonSm from "@/components/ui-components/ButtonSm";
import SubactionHeader from '@/components/ui-components/SubactionHeader';

import MOCAPthreeDReconstructionSettings from "@/components/mocap-setup/mocap-3dreconstruction-settings";
import MOCAPMediaPipeDetectorSettings from "@/components/mocap-setup/mocap-mediapipedetector-settings";

interface MocapSetupModalProps {
  onClose?: () => void;
}

const MocapSetupModal: React.FC<MocapSetupModalProps> = ({ onClose }) => {
  const [activeButton, setActiveButton] = useState<"button1" | "button2" | "button3">("button1");
  const [row2Active, setRow2Active] = useState<"left" | "right">("left");

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
        return (
          <div className="flex flex-col gap-2 p-2 bg-dark br-2">
            <p className="text-white text md">Third Settings Panel</p>
            <p className="text-gray text sm">Placeholder for additional settings content.</p>
            <div className="flex flex-col gap-1 mt-2">
              <div className="flex items-center gap-2">
                <span className="icon settings-icon icon-size-20" />
                <p className="text-gray text sm">Sample setting option 1</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="icon settings-icon icon-size-20" />
                <p className="text-gray text sm">Sample setting option 2</p>
              </div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <>
      {/* Backdrop overlay */}
      <div 
        className="pos-fixed inset-0" 
        style={{ 
          backgroundColor: "rgba(0, 0, 0, 0.7)", 
          zIndex: 999,
          backdropFilter: "blur(4px)"
        }}
        onClick={onClose}
      />
      
      {/* Modal */}
      <div 
        className="mocap-settings-modal pos-fixed elevated-sharp p-1 b-2" 

      >
        {/* <div className="flex items-center justify-content-space-between p-3 border-1 border-bottom" style={{ borderColor: "var(--color-border-secondary)" }}>
          <h3 className="text-white text lg">Mocap Setup</h3>
          <ButtonSm text="Close" iconClass="clear-icon" buttonType="secondary" onClick={onClose} />
        </div> */}

        {/* Row 1 */}
        <div className="flex flex-row gap-2 p-3" style={{ minHeight: 400 }}>
          {/* Column 1 - Buttons */}
            

          <div className="flex flex-col gap-2" style={{ minWidth: 180, flexShrink: 0 }}>
            <SubactionHeader 
            text="Mocap setup" 
            className="text-white"/>
            <ButtonSm
              text="3D Reconstruction"
              buttonType={activeButton === "button1" ? "primary" : "secondary"}
              className="full-width"
              onClick={() => setActiveButton("button1")}
            />
            <ButtonSm
              text="MediaPipe Detector"
              buttonType={activeButton === "button2" ? "primary" : "secondary"}
              className="full-width"
              onClick={() => setActiveButton("button2")}
            />
            <ButtonSm
              text="Other Settings"
              buttonType={activeButton === "button3" ? "primary" : "secondary"}
              className="full-width"
              onClick={() => setActiveButton("button3")}
            />
          </div>
          
          {/* Column 2 - Dynamic Content */}
          <div className="right-side-settings-container flex w-full flex-row">
            {renderRightPanelContent()}
          </div>
        </div>

        {/* Row 2 */}
        <div className="flex flex-row gap-2 p-3 pt-0">
          {/* Column 1 - Two buttons */}
          <div className="flex flex-row gap-2" style={{ minWidth: 180, flexShrink: 0 }}>
            <ButtonSm
              text="Action A"
              buttonType={row2Active === "left" ? "primary" : "secondary"}
              className="full-width"
              onClick={() => setRow2Active("left")}
            />
            <ButtonSm
              text="Action B"
              buttonType={row2Active === "right" ? "primary" : "secondary"}
              className="full-width"
              onClick={() => setRow2Active("right")}
            />
          </div>
          
          {/* Column 2 - Paragraph */}
          <div className="flex-1 bg-dark br-2 p-2 flex items-center">
            <p className="text-gray text md text-center w-full">
              This is a dummy paragraph. Content changes based on which action button is active. Currently:{" "}
              <span className="text-white">{row2Active === "left" ? "Action A" : "Action B"}</span>
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default MocapSetupModal;