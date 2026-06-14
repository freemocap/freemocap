import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ValueSelector from "@/components/ui-components/ValueSelector";
import IconButton from "@/components/ui-components/IconButton";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";
import { useCalibration } from "@/hooks/useCalibration";
import { CalibrationSolverMethod } from "@/store/slices/calibration";

type BoardPreset = "5 x 3" | "7 x 5" | "Custom";

interface BoardPresetDims {
  squares_x: number;
  squares_y: number;
}

const BOARD_PRESETS: Record<Exclude<BoardPreset, "Custom">, BoardPresetDims> = {
  "5 x 3": { squares_x: 5, squares_y: 3 },
  "7 x 5": { squares_x: 7, squares_y: 5 },
};

const PRESET_OPTIONS: BoardPreset[] = ["5 x 3", "7 x 5", "Custom"];

const PRESET_OPTIONS_SOLVER = ["Anipose legacy", "Accurate"];

const solverLabelToMethod: Record<string, CalibrationSolverMethod> = {
  "Anipose legacy": "anipose",
  "Accurate": "pyceres",
};

const solverMethodToLabel: Record<CalibrationSolverMethod, string> = {
  anipose: "Anipose legacy",
  pyceres: "Accurate",
};

interface CalibrationSettingsProps {
  onClose?: () => void;
}

const CalibrationSettings = ({ onClose }: CalibrationSettingsProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const { config, updateCalibrationConfig } = useCalibration();
  const board = config.charucoBoard;

  const handleClose = useCallback(() => {
    if (onClose) onClose();
  }, [onClose]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
        handleClose();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") handleClose();
    };

    document.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleClose]);

  const currentPreset = useMemo<BoardPreset>(() => {
    for (const [preset, dims] of Object.entries(BOARD_PRESETS)) {
      if (dims.squares_x === board.squares_x && dims.squares_y === board.squares_y) {
        return preset as BoardPreset;
      }
    }
    return "Custom";
  }, [board.squares_x, board.squares_y]);

  const [forcedCustom, setForcedCustom] = useState(false);

  const displayedPreset: BoardPreset = forcedCustom ? "Custom" : currentPreset;

  const handlePresetChange = useCallback(
    (value: string) => {
      const preset = value as BoardPreset;
      if (preset === "Custom") {
        setForcedCustom(true);
        return;
      }
      setForcedCustom(false);
      updateCalibrationConfig({
        charucoBoard: { ...board, ...BOARD_PRESETS[preset] },
      });
    },
    [board, updateCalibrationConfig],
  );

  const handleSolverChange = useCallback(
    (value: string) => {
      const method = solverLabelToMethod[value];
      if (method) updateCalibrationConfig({ solverMethod: method });
    },
    [updateCalibrationConfig],
  );

  return (
    <div
      className="z-10 calibration-settings-flyout pos-fixed draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
    >
      <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1" ref={modalRef} onClick={(e) => e.stopPropagation()}>
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
            key={displayedPreset}
            options={PRESET_OPTIONS}
            initialValue={displayedPreset}
            onChange={handlePresetChange}
            className="flex flex-row"
          />
        </div>

        {/* X Square Size */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">X Square Size</span>
          <ValueSelector
            value={board.squares_x}
            min={2}
            max={20}
            step={1}
            unit=""
            disabled={displayedPreset !== "Custom"}
            onChange={(v) => updateCalibrationConfig({ charucoBoard: { ...board, squares_x: v } })}
          />
        </div>

        {/* Y Square Size */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Y Square Size</span>
          <ValueSelector
            value={board.squares_y}
            min={2}
            max={20}
            step={1}
            unit=""
            disabled={displayedPreset !== "Custom"}
            onChange={(v) => updateCalibrationConfig({ charucoBoard: { ...board, squares_y: v } })}
          />
        </div>

        <SubactionHeader text="Board Dimensions" />

        {/* Square length */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Square length</span>
          <ValueSelector
            value={board.square_length_mm}
            min={1}
            max={9999999}
            step={0.1}
            unit="mm"
            onChange={(v) => updateCalibrationConfig({ charucoBoard: { ...board, square_length_mm: v } })}
          />
        </div>

        <SubactionHeader text="Solver settings" />

        {/* Method dropdown */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Method</span>
          <NameDropdownSelector
            key={config.solverMethod}
            options={PRESET_OPTIONS_SOLVER}
            initialValue={solverMethodToLabel[config.solverMethod]}
            onChange={handleSolverChange}
            className="flex flex-row"
          />
        </div>
      </div>
    </div>
  );
};

export default CalibrationSettings;
