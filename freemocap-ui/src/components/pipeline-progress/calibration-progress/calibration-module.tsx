import React, { useState } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";
import IconButton from "@/components/ui-components/IconButton";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";
import CalibrationSettings from "./calibration-settings";
import ButtonSm from "@/components/ui-components/ButtonSm";

const CalibrationModule = () => {
  const [isElectron] = useState(true); // Added missing state variable

  return (
      <div className="flex flex-col p-1 bg-middark br-1">
        {/* Content goes here */}
        <div className="flex flex-row items-center">
          <div className="flex flex-row flex-1 justify-content-space-between items-center w-100">
            <SubactionHeader text="Calibration" />
            <div className="flex flex-row gap-1 items-center">
              <IconButton
                icon="explainer-icon"
                className="button sm mr-1"
                onClick={() => {}} // shows onboarding tooltips
                tooltip
                tooltipText="How to calibrate"
                tooltipPosition="pos-left"
              />
            </div>
          </div>
        </div>
        <div className="flex p-1 br-1 h-25 flex-row items-center justify-content-space-between">
          <div className="group-1 flex flex-col items-start">
            <p className="text-gray text-nowrap text md text-align-left">
              Charuco board
            </p>
          </div>
          <div className="group-2 flex flex-row items-center gap-1">
            <div className="group-2.1 charuco-settings-action-container flex flex-row items-center gap-1">
              <span className="text-gray tag text-nowrap text md text-align-left">
                5x3
              </span>
              <span className="text-gray tag text-nowrap text md text-align-left">
                35mm
              </span>
              <span className="text-gray tag text-nowrap text md text-align-left">
                Anipose
              </span>
            </div>
            <div className="group-2.2 flex flex-col items-center">
              <IconButton
                icon="settings-icon"
                className="button sm"
                onClick={() => {}} // Does nothing but clicks
                tooltip
                tooltipText="Charuco settings"
                tooltipPosition="pos-left"
              />
            </div>
          </div>
        </div>
        <div className="p-1 group-3 calibration-action-container flex flex-row items-center">
          <ButtonSm
            iconClass="charuco-icon"
            text="Calibrate"
            onClick={() => {}} // Does nothing but clicks
            disabled={!isElectron}
            className="button sm min-w-full justify-center"
            buttonType="secondary"
            textClass="text-center text md"
          />
        </div>
      </div>
    // </div>
  );
};

export default CalibrationModule;