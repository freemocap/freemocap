import React, { useState } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";
import IconButton from "@/components/ui-components/IconButton";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";

const CalibrationSettings = ({ onClose }) => {
  // UI-only state for visual interactions
  const [currentPreset, setCurrentPreset] = useState("7 x 5");
  const [currentPresetSolver, setCurrentPresetSolver] =
    useState("Anipose legacy");
  const [xSquareSize, setXSquareSize] = useState(5);
  const [ySquareSize, setYSquareSize] = useState(3);
  const [squareLength, setSquareLength] = useState(35);
  const [betaValue, setBetaValue] = useState(2.5);

  const handleClose = () => {
    if (onClose) onClose();
  };

  const PRESET_OPTIONS = ["5 x 3", "7 x 5", "Custom"];
  const PRESET_OPTIONS_SOLVER = ["Anipose legacy", "Accurate"];

  const presetValueToLabel: Record<string, string> = {
    "7 x 5": "7 x 5",
    "5 x 3": "5 x 3",
    custom: "Custom",
  };

  // UI-only handlers that just update local state
  const handlePresetChange = (value: string) => {
    setCurrentPreset(value);
  };

  const handlePresetChangeSolver = (value: string) => {
    setCurrentPresetSolver(value);
  };

  return (
    <div
      className="z-10 calibration-settings-flyout pos-fixed draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
      onClick={handleClose}
    >
      <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex flex-row justify-content-space-between items-center">
          <div className="flex flex-row flex-1 justify-content-space-between items-center w-100">
            <SubactionHeader text="Charuco board settings" />
            <div className="flex flex-row gap-1 items-center">
              <IconButton
                icon="explainer-icon"
                className="button sm"
                onClick={() => {}} // Does nothing but clicks
                tooltip
                tooltipText="Learn about calibration"
                tooltipPosition="pos-left"
              />
            </div>
          </div>
        </div>

        {/* Preset dropdown */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Preset</span>
          <NameDropdownSelector
            key={currentPreset}
            options={PRESET_OPTIONS}
            initialValue={currentPreset}
            onChange={handlePresetChange}
            className="flex flex-row"
          />
        </div>

        {/* X Square Size */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">X Square Size</span>
          <ValueSelector
            value={xSquareSize}
            min={1}
            max={200}
            step={1}
            unit=""
            onChange={setXSquareSize}
          />
        </div>

        {/* Y Square Size */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Y Square Size</span>
          <ValueSelector
            value={ySquareSize}
            min={1}
            max={200}
            step={1}
            unit=""
            onChange={setYSquareSize}
          />
        </div>

        <SubactionHeader text="Board Dimensions" />

        {/* Square length */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Square length</span>
          <ValueSelector
            value={squareLength}
            min={1}
            max={9999999}
            step={1}
            unit="mm"
            onChange={setSquareLength}
          />
        </div>

        {/* Beta */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Beta</span>
          <ValueSelector
            value={betaValue}
            min={0}
            max={5}
            step={0.05}
            unit=""
            onChange={setBetaValue}
          />
        </div>

        <SubactionHeader text="Solver settings" />

        {/* Method dropdown */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Method</span>
          <NameDropdownSelector
            key={currentPresetSolver}
            options={PRESET_OPTIONS_SOLVER}
            initialValue={currentPresetSolver}
            onChange={handlePresetChangeSolver}
            className="flex flex-row"
          />
        </div>
      </div>
    </div>
  );
};

export default CalibrationSettings;
