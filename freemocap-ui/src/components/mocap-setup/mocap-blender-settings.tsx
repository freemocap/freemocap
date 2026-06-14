import React, { useEffect, useRef } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ButtonSm from "@/components/ui-components/ButtonSm";
import { useMocap } from "@/hooks/useMocap";
import { useBlender } from "@/hooks/useBlender";
import { useElectronIPC } from "@/services";

interface MOCAPBlenderSettingsProps {
  open: boolean;
  onClose: () => void;
}

const MOCAPBlenderSettings: React.FC<MOCAPBlenderSettingsProps> = ({
  open,
  onClose,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);

  const { mocapRecordingPath } = useMocap();
  const { api, isElectron } = useElectronIPC();
  const {
    effectiveBlenderExePath,
    isUsingManualBlenderPath,
    exportToBlenderEnabled,
    autoOpenBlendFile,
    isExporting,
    isDetecting,
    isOpening,
    lastBlendFilePath,
    redetectBlender,
    setBlenderExePath,
    clearBlenderExePath,
    setExportToBlenderEnabled,
    setAutoOpenBlendFile,
    triggerBlenderExport,
    triggerOpenInBlender,
  } = useBlender();

  const handleSelectBlenderExe = async (): Promise<void> => {
    if (!isElectron || !api) return;
    try {
      const result: string | null = await api.fileSystem.selectExecutableFile.mutate();
      if (result) setBlenderExePath(result);
    } catch (error) {
      console.error("Failed to select Blender executable:", error);
    }
  };

  const handleProcessWithBlender = (): void => {
    if (!mocapRecordingPath) return;
    void triggerBlenderExport(mocapRecordingPath);
  };

  const handleOpenInBlender = (): void => {
    if (!mocapRecordingPath) return;
    void triggerOpenInBlender(mocapRecordingPath);
  };

  const canExport =
    !!mocapRecordingPath && !!effectiveBlenderExePath && !isExporting;

  const canOpen =
    !!mocapRecordingPath && !!effectiveBlenderExePath && !isOpening;

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
      className="flex flex-col w-full br-2 reveal fadeIn gap-1"
    >
      <div className="gap-1 flex flex-col">
        {/* Header */}
        <div className="flex justify-content-space-between items-center">
          <SubactionHeader text="Blender settings" />
        </div>
        <div className="flex flex-row justify-content-space-between items-center">
          <div className="flex flex-row items-center">
            <span className="icon icon-size-20 blender-icon"></span>
            <p className="p-1 text-gray">Blender executable</p>
          </div>
          <ButtonSm
            text={isDetecting ? "Detecting..." : "Autodetect"}
            onClick={redetectBlender}
            disabled={isDetecting}
          />
        </div>

        {/* Blender executable selector */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <button
            className="select-path button sm bg-middark br-1 border-1 border-black flex items-center gap-1 text-left flex-1"
            onClick={handleSelectBlenderExe}
            title="Click to select Blender executable"
            disabled={!isElectron}
            style={{ minWidth: 0, overflow: "hidden" }}
          >
            {effectiveBlenderExePath ? (
              <p
                className="recording-path-preview flex-1 text md"
                style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              >
                {effectiveBlenderExePath}
              </p>
            ) : (
              <p
                className="text-gray flex-1 text md"
                style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              >
                {isDetecting ? "Detecting…" : "Select Blender executable"}
              </p>
            )}
          </button>
          {isUsingManualBlenderPath && (
            <div className="flex flex-row gap-1" style={{ flexShrink: 0 }}>
              <IconButton
                icon="clear-icon"
                onClick={clearBlenderExePath}
                title="Clear manual path (revert to auto-detected)"
              />
            </div>
          )}
        </div>
        <p className="text sm text-gray">
          {isUsingManualBlenderPath
            ? "Using manually selected Blender"
            : effectiveBlenderExePath
              ? "Auto-detected Blender"
              : "Click to browse for blender.exe"}
        </p>

        {/* Toggles */}
        <ToggleComponent
          text="Export to Blender after mocap processing"
          isToggled={exportToBlenderEnabled}
          onToggle={setExportToBlenderEnabled}
        />

        <ToggleComponent
          text="Auto-open .blend file in Blender when done"
          isToggled={autoOpenBlendFile}
          onToggle={setAutoOpenBlendFile}
        />

        <ButtonSm
          text={isExporting ? "Exporting to Blender…" : "Process Recording with Blender"}
          onClick={handleProcessWithBlender}
          disabled={!canExport}
          className="full-width quaternary"
        />

        <ButtonSm
          text={isOpening ? "Opening…" : "Open .blend in Blender"}
          onClick={handleOpenInBlender}
          disabled={!canOpen}
          className="full-width quaternary"
        />

        {lastBlendFilePath && (
          <p className="text sm text-gray" style={{ fontFamily: "monospace" }}>
            Last export: {lastBlendFilePath}
          </p>
        )}
      </div>
    </div>
  );
};

export default MOCAPBlenderSettings;
