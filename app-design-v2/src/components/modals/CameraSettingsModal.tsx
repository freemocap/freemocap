/*
 * ::::: by  Pooya Deperson 2025  <pooyadeperson@gmail.com> :::::
 *
 *  React Component: CameraSettingsModal
 *
 *  PURPOSE:
 *     A draggable modal window for controlling camera parameters such as
 *     resolution, exposure mode, and manual exposure adjustment.
 *     It integrates with the custom `useDraggableTooltips` hook to allow
 *     users to reposition the modal freely on the screen.
 *
 * HOW TO USE (React):
 *     1. Import and render the modal anywhere in your app where camera
 *        configuration is needed.
 *
 *        ```jsx
 *        import CameraSettingsModal from "@/components/modals/CameraSettingsModal";
 *
 *        export default function CameraPage() {
 *          return (
 *            <CameraSettingsModal
 *              onRotate={() => console.log("Rotate camera")}
 *              onClose={() => console.log("Close modal")}
 *            />
 *          );
 *        }
 *        ```
 *
 *     2. The modal automatically becomes draggable via `useDraggableTooltips()`.
 *        You can click and drag the modal by grabbing anywhere on it.
 *
 *  FEATURES:
 *     -  Resolution Selector — choose from predefined resolutions.
 *     -  Exposure Selector — toggle between “Auto”, “Manual”, or “Recommended”.
 *     -  Manual Exposure Adjustment — numeric selector (only active when exposure = Manual).
 *     -  Rotate Button — triggers the optional `onRotate` callback.
 *     -  Close Button — triggers the optional `onClose` callback.
 *
 */


import React, { useState, useEffect } from "react";
import clsx from "clsx";
import ValueSelector from "../uicomponents/ValueSelector";
import SubactionHeader from "../uicomponents/SubactionHeader";
import NameDropdownSelector from "../uicomponents/NameDropdownSelector";
import useDraggableTooltips from "../hooks/useDraggableTooltips";

interface CameraSettingsModalProps {
  onRotate?: () => void;
  onClose?: () => void;
}

const Resolution = ({
  selectedResolution,
  setSelectedResolution,
}: {
  selectedResolution: string;
  setSelectedResolution: React.Dispatch<React.SetStateAction<string>>;
}) => {
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

const Exposure = ({
  selectedExposure,
  setSelectedExposure,
}: {
  selectedExposure: string;
  setSelectedExposure: React.Dispatch<React.SetStateAction<string>>;
}) => {
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

const CameraSettingsModal: React.FC<CameraSettingsModalProps> = ({
  onRotate,
  onClose,
}) => {
  const [selectedResolution, setSelectedResolution] = useState("1920 × 1080");
  const [selectedExposure, setSelectedExposure] = useState("Auto");
  const [autoIncrementValue, setAutoIncrementValue] = useState(0);

  // 🧩 Enable dragging when modal mounts
  useDraggableTooltips();

  // 🧠 Optionally make sure modal is `.draggable`
  useEffect(() => {
    const modalEl = document.querySelector(
      ".camera-settings-modal"
    ) as HTMLElement | null;
    if (modalEl && !modalEl.classList.contains("draggable")) {
      modalEl.classList.add("draggable");
    }
  }, []);

  return (
    <div className="reveal slide-down camera-settings-modal modal draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1 z-2">
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

          {/* Change exposure (enabled only when Manual) */}
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
              />
          </div>

          {/* Optional close button */}
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
