import React, { useState, useRef, useEffect, useCallback } from "react";
import ButtonSm from "@/components/ui-components/ButtonSm";
import SubactionHeader from "@/components/ui-components/SubactionHeader";

import CalibrationModule from "@/components/pipeline-progress/calibration-progress/calibration-module";
import MOCAPthreeDReconstructionSettings from "@/components/mocap-setup/mocap-3dreconstruction-settings";
import MOCAPMediaPipeDetectorSettings from "@/components/mocap-setup/mocap-mediapipedetector-settings";
import MOCAPBlenderSettings from "@/components/mocap-setup/mocap-blender-settings";

interface MocapSetupModalProps {
  onClose?: () => void;
}

const MocapSetupModal: React.FC<MocapSetupModalProps> = ({ onClose }) => {
  const [activeButton, setActiveButton] = useState<
    "button1" | "button2" | "button3" | "button4"
  >("button1");

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const panel1Ref = useRef<HTMLDivElement>(null);
  const panel2Ref = useRef<HTMLDivElement>(null);
  const panel3Ref = useRef<HTMLDivElement>(null);
  const panel4Ref = useRef<HTMLDivElement>(null);

  const scrollToPanel = useCallback((panelIndex: number) => {
    const refs = [panel1Ref, panel2Ref, panel3Ref, panel4Ref];
    const targetRef = refs[panelIndex];
    if (targetRef.current && scrollContainerRef.current) {
      targetRef.current.scrollIntoView({
        behavior: "smooth",
        block: "start",
        inline: "nearest",
      });
      setActiveButton(
        ["button1", "button2", "button3", "button4"][panelIndex] as
          | "button1"
          | "button2"
          | "button3"
          | "button4",
      );
    }
  }, []);

  // IntersectionObserver to detect which panel is visible on scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute("data-panel");
            if (id === "panel1") setActiveButton("button1");
            else if (id === "panel2") setActiveButton("button2");
            else if (id === "panel3") setActiveButton("button3");
            else if (id === "panel4") setActiveButton("button4");
          }
        });
      },
      {
        root: scrollContainerRef.current,
        rootMargin: "0px 0px -50% 0px",
        threshold: 0.5,
      },
    );

    const panels = [panel1Ref, panel2Ref, panel3Ref, panel4Ref];
    panels.forEach((ref) => {
      if (ref.current) observer.observe(ref.current);
    });

    return () => {
      observer.disconnect();
    };
  }, []);

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="pos-fixed inset-0 bg-surface-overlay z-10"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="mocap-settings-modal bg-primary border-1 border-black overflow-hidden pos-fixed gap-1 elevated-sharp p-1 b-2 flex flex-col br-2">
        {/* Row 1 */}
        <div className="inner-container-settings gap-1 flex flex-row flex-1 br-2">
          {/* Column 1 - Buttons */}
          <div
            className="left-section-actions br-1 p-2 bg-tertiary flex flex-col flex-1 gap-2"
            style={{ maxWidth: 146, flexShrink: 0 }}
          >
            <SubactionHeader text="Mocap setup" className="text-gray" />
            <ButtonSm
              text="Calibration"
              buttonType={activeButton === "button1" ? "activated" : "idle"}
              className="full-width quaternary"
              onClick={() => scrollToPanel(0)}
            />
            <ButtonSm
              text="3D Reconstruction"
              buttonType={activeButton === "button2" ? "activated" : "idle"}
              className="full-width quaternary"
              onClick={() => scrollToPanel(1)}
            />
            <ButtonSm
              text="MediaPipe Detector"
              buttonType={activeButton === "button3" ? "activated" : "idle"}
              className="full-width quaternary"
              onClick={() => scrollToPanel(2)}
            />
            <ButtonSm
              text="Blender"
              buttonType={activeButton === "button4" ? "activated" : "idle"}
              className="full-width quaternary"
              onClick={() => scrollToPanel(3)}
            />
          </div>

          {/* Column 2 - Dynamic Content */}
          <div
            ref={scrollContainerRef}
            className="right-side-settings-container bg-primary br-1 overflow-y flex-1 flex flex-col gap-1 w-full flex-row overflow-y-auto"
          >
            {/* <div className="flex flex-col gap-2 w-full"> */}
            {/* Panel 1 - Calibration */}
            <div
              ref={panel1Ref}
              data-panel="panel1"
              className="bg-secondary p-2 br-1"
            >
              <CalibrationModule />
            </div>

            {/* Panel 2 - 3D Reconstruction */}
            <div
              ref={panel2Ref}
              data-panel="panel2"
              className="bg-secondary p-2 br-1"
            >
              <MOCAPthreeDReconstructionSettings
                open={true}
                onClose={() => {}}
              />
            </div>

            {/* Panel 3 - MediaPipe Detector */}
            <div
              ref={panel3Ref}
              data-panel="panel3"
              className="bg-secondary p-2 br-1"
            >
              <MOCAPMediaPipeDetectorSettings open={true} onClose={() => {}} />
            </div>

            {/* Panel 4 - Blender */}
            <div
              ref={panel4Ref}
              data-panel="panel4"
              className="bg-secondary p-2 br-1"
            >
              <MOCAPBlenderSettings open={true} onClose={() => {}} />
            </div>

            {/* Dummy div for extra scroll space */}
            <div
              className="bg-secondary p-2"
              style={{ minHeight: "220px", transform: "translateY(-6px)" }}
            ></div>
            {/* </div> */}
          </div>
        </div>

        {/* Row 2 */}
        <div className="bottom-area-action-container p-2 br-2 flex flex-col align-end bottom-row gap-2 pt-0">
          {/* Column 1 - Two buttons */}
          <div className="flex flex-row gap-2 h-full">
            <ButtonSm
              text="Cancel"
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
            <p className="text sm text-gray">
              Processing may take hours, depending on your system, ideally avoid
              using your computer.
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default MocapSetupModal;
