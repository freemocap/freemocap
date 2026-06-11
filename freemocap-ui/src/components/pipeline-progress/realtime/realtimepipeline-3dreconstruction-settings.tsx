import React, { useEffect, useRef, useState } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";

interface RTPMediaPipeDetectorSettingsProps {
  open: boolean;
  onClose: () => void;
}

const RTPMediaPipeDetectorSettings: React.FC<
  RTPMediaPipeDetectorSettingsProps
> = ({ open, onClose }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  // Toggles
  const [smoothLandmarks, setSmoothLandmarks] = useState(true);
  const [segmentation, setSegmentation] = useState(true);
  const [smoothSegmentation, setSmoothSegmentation] = useState(true);
  const [refineFaceLandmarks, setRefineFaceLandmarks] = useState(true);
  const [staticImageMode, setStaticImageMode] = useState(true);

  // Dropdown state (IMPORTANT FIX)
  const [preset, setPreset] = useState("Lite Fastest");

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={modalRef}
      className="RTP-settings-flyout pos-abs top-5 right-0 draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
    >
      <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1">
        {/* Header */}
        <div className="flex justify-content-space-between items-center">
          <SubactionHeader text="Point Gate settings" />
          <button className="button icon-button" onClick={onClose}>
            <span className="icon close-icon icon-size-20" />
          </button>
        </div>

        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max Reprok Error</span>

          <ValueSelector
            value={39}
            min={1}
            max={500}
            unit="px"
            onChange={() => {}}
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max Velocity</span>

          <ValueSelector
            value={50}
            min={1}
            max={500}
            unit="m/s"
            onChange={() => {}}
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max Rejected streaks</span>

          <ValueSelector
            value={5}
            min={1}
            max={20}
            unit=""
            onChange={() => {}}
          />
        </div>

        <SubactionHeader text="One Euro Filter" />
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Min Cutoff</span>
          <ValueSelector
            value={0.005}
            min={0.00000001}
            max={20.0}
            unit=""
            onChange={() => {}}
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Beta</span>
          <ValueSelector
            value={0.3}
            min={0.01}
            max={20.0}
            unit=""
            onChange={() => {}}
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">D Cutoff</span>
          <ValueSelector
            value={1}
            min={1}
            max={100}
            unit=""
            onChange={() => {}}
          />
        </div>

        <SubactionHeader text="Fabrik" />
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max iterations</span>
          <ValueSelector
            value={20}
            min={0}
            max={1}
            unit=""
            onChange={() => {}}
          />
        </div>

        <SubactionHeader text="Body Model" />
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Height</span>
          <ValueSelector
            value={1.75}
            min={1}
            max={20}
            unit="m"
            onChange={() => {}}
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Noise sigma</span>
          <ValueSelector
            value={0.015}
            min={0.0001}
            max={9.9999}
            unit="m"
            onChange={() => {}}
          />
        </div>

        <ToggleComponent
          text="Skeleton"
          isToggled={staticImageMode}
          onToggle={setStaticImageMode}
        />
      </div>
    </div>
  );
};

export default RTPMediaPipeDetectorSettings;
