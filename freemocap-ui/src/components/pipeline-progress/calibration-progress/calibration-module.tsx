import React, { useState } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";
import IconButton from "@/components/ui-components/IconButton";
import DropdownButton from "@/components/ui-components/DropdownButton.tsx";
import CalibrationSettings from "./calibration-settings";
import ButtonSm from "@/components/ui-components/ButtonSm";

const CalibrationModule = () => {
  const [isElectron] = useState(true); // Added missing state variable
  const [showCalibrationSettings, setShowCalibrationSettings] = useState(false);
  const [isCalibrated, setIsCalibrated] = useState(true); // Set to false for now

  const handleToggleSettings = () => {
    setShowCalibrationSettings(!showCalibrationSettings);
  };

  const handleCloseSettings = () => {
    setShowCalibrationSettings(false);
  };

  const dropdownItems = (
    <div className="flex flex-col gap-1">
      <ButtonSm
        iconClass="record-icon"
        text="Record and Calibrate"
        className="full-width"
        textClass="text-align-left"
        onClick={() => {}}
      />
      <ButtonSm
        iconClass="importVideos-icon"
        text="Import Calibration videos"
        className="full-width"
        textClass="text-align-left"
        onClick={() => {}}
      />
      <ButtonSm
        iconClass="tomlfile-icon"
        text="Import .toml file"
        className="full-width"
        textClass="text-align-left"
        onClick={() => {}}
      />
    </div>
  );

  // If calibrated, show dummy UI
  if (isCalibrated) {
    return (
      <div className="flex flex-col p-1 bg-middark br-1 pos-rel">
        <div className="flex flex-row items-center">
          <div className="flex flex-row flex-1 justify-content-space-between items-center w-100">
            <div className="flex flex-row items-center">
              <div className="calibrate-icon-group flex flex-row items-center">
                <span className="icon calibrated-icon icon-size-20" />
                <p className="text md text-success p-1">Calibrated</p>
              </div>
              <div className="calibrated-path-group flex flex-row items-center">
                <p className="text md text-nowrap flex flex-row w-full text-gray p-1">
                  C:Path:where-it-was-calibared-
                </p>
              </div>
            </div>
            <div className="flex flex-row gap-1 items-center">
              <IconButton
                icon="explainer-icon"
                className="button sm"
                onClick={() => {}} // shows onboarding tooltips
                tooltip
                tooltipText="How to calibrate"
                tooltipPosition="pos-left"
              />
            </div>
          </div>
        </div>
        <div className="groupe-2-action- flex flex-row pos-rel justify-content-space-between items-center gap-1">
          <div className="flex flex-row items-center how-it-was-made-group">
            <div className="how-it-was-made-inner-group pos-rel flex flex-row items-center">
              <span className="icon record-icon icon-size-20" />
              {/* This is important, change icon
              and show how it was originally the calibration done
              like
              if done by recording show record-icon
              if used videos show importVideos-icon
              if used by importing toml file show tomlfile-icon
              */}
              <span className="icon snaptogrid-icon icon-size-20" />
            </div>
            <div className="charuco-group-on-it-was-adhjusted- charuco-settings-action-container flex flex-row items-center gap-1">
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
          </div>
             <IconButton
            icon="cancelcalibrate-icon"
            className="button sm"
            onClick={() => {}} // shows onboarding tooltips
            tooltip
            tooltipText="Abort Calibration"
            tooltipPosition="pos-left"
          />
        </div>
        
      </div>
    );
  }

  // Original UI when not calibrated
  return (
    <div className="flex flex-col p-1 bg-middark br-1 pos-rel ">
      {/* Content goes here */}
      <div className="flex flex-row items-center">
        <div className="flex flex-row flex-1 justify-content-space-between items-center w-100">
          <SubactionHeader text="Calibration" />
          <div className="flex flex-row gap-1 items-center">
            <IconButton
              icon="explainer-icon"
              className="button sm"
              onClick={() => {}} // shows onboarding tooltips
              tooltip
              tooltipText="How to calibrate"
              tooltipPosition="pos-left"
            />
          </div>
        </div>
      </div>
      <div
        className="button sm trigger-charuco-settings-flyout flex-wrap flex pos-rel p-1 br-1 flex-row items-center justify-content-space-between"
        onClick={handleToggleSettings}
      >
        <div className="group-1 flex flex-col items-start">
          <p className="text-gray text-nowrap text md text-align-left">
            Charuco board
          </p>
        </div>
        <div className="group-2 flex flex-row pos-rel items-center gap-1">
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
          <div className="group-2.2 pos-rel flex flex-col items-center">
            <span className="icon settings-icon icon-size-20" />
          </div>
        </div>
      </div>
      {showCalibrationSettings && (
        <CalibrationSettings onClose={handleCloseSettings} />
      )}
      <div className="p-1 group-3 calibration-action-container flex flex-row items-center">
        <DropdownButton
          buttonProps={{
            text: "Calibrate",
            iconClass: "charuco-icon",
            disabled: !isElectron,
            className: "button sm min-w-full justify-center",
            buttonType: "secondary",
            textClass: "text-center text md",
          }}
          dropdownItems={dropdownItems}
          dropdownClassName=""
        />
      </div>
      <ToggleComponent
        text="Align to initial Charuco ground plane"
        className=""
        iconClass="snaptogrid-icon"
        defaultToggelState=""
        isToggled=""
        onToggle=""
        disabled=""
      />
    </div>
  );
};

export default CalibrationModule;
