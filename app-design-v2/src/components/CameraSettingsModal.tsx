import React, { useState } from "react";
import clsx from "clsx";
import {
  ValueSelector,
  SubactionHeader,
  NameDropdownSelector,
} from "./uicomponents";

const Resolution = ({ selectedResolution, setSelectedResolution }) => {
  const options = ["1920 × 1080", "1280 × 720", "640 × 480"];

  return (
    <div className="flex flex-col">
      <div className="dropdown-container">
        <NameDropdownSelector
          options={options}
          initialValue={selectedResolution}
          onChange={setSelectedResolution}
        />
      </div>
    </div>
  );
};

const Exposure = ({ selectedExposure, setSelectedExposure }) => {
  const options = ["Auto", "Manual", "Recommended"];

  return (
    <div className="flex flex-col">
      <div className="dropdown-container">
        <NameDropdownSelector
          options={options}
          initialValue={selectedExposure}
          onChange={setSelectedExposure}
        />
      </div>
    </div>
  );
};

interface CameraSettingsModalProps {
  onRotate?: () => void;
  onClose?: () => void;
}

const CameraSettingsModal: React.FC<CameraSettingsModalProps> = ({
  onRotate,
  onClose,
}) => {
  const [selectedResolution, setSelectedResolution] = useState("1920 × 1080");
  const [selectedExposure, setSelectedExposure] = useState("Auto");
  const [autoIncrementValue, setAutoIncrementValue] = useState(0);

  return (
    <div className="reveal slide-down camera-settings-modal modal border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1 z-2">
      <div className="flex flex-col right-0 p-2 gap-1 bg-middark br-1 z-1">
        <div className="subaction-group flex flex-col flex-1 gap-1 mb-4">
          <SubactionHeader text="Camera settings" />

          {/* Rotate button */}
          <div className="toggle-button button text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
            <div className="text-container overflow-hidden flex items-center">
              <p className="text text-nowrap text-left md">Rotate</p>
            </div>
            <button
              onClick={onRotate}
              className="button icon-button rotate-button"
            >
              <span className="icon rotate-icon icon-size-16"></span>
            </button>
          </div>

          {/* Resolution selector */}
          <div className="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
            <div className="gap-1 text-container overflow-hidden flex items-center">
              <p className="text text-nowrap text-left md">Resolution</p>
            </div>
            <Resolution
              selectedResolution={selectedResolution}
              setSelectedResolution={setSelectedResolution}
            />
          </div>

          {/* Exposure selector */}
          <div className="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
            <div className="gap-1 text-container overflow-hidden flex items-center">
              <p className="text text-nowrap text-left md">Exposure</p>
            </div>
            <Exposure
              selectedExposure={selectedExposure}
              setSelectedExposure={setSelectedExposure}
            />
          </div>

          {/* Change exposure (enabled only when NOT Auto) */}
          <div
            className={clsx(
              "text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center h-25",
              { disabled: selectedExposure !== "Manual" }
            )}
          >
            <div className="gap-1 text-container overflow-hidden flex items-center">
              <span className="icon icon-size-16 subcat-icon"></span>
              <p className="text text-nowrap text-left md">Change exposure</p>
            </div>
            <ValueSelector
              unit=""
              min={-17}
              max={17}
              initialValue={autoIncrementValue}
              value={autoIncrementValue}
              onChange={setAutoIncrementValue}
              disabled={selectedExposure === "Auto"}
            />
          </div>

          {/* Optional close button inside modal */}
          {onClose && (
            <button
              className="button icon-button close-button absolute top-1 right-1"
              onClick={onClose}
            >
              <span className="icon close-icon icon-size-16"></span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default CameraSettingsModal;
