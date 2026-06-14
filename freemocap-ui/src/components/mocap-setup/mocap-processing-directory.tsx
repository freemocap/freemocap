import React, { useEffect, useRef } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import { useMocap } from "@/hooks/useMocap";
import { useElectronIPC } from "@/services";

interface ProcessDirectoryModuleProps {
  open: boolean;
  onClose: () => void;
}

const ProcessDirectoryModule: React.FC<ProcessDirectoryModuleProps> = ({
  open,
  onClose,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);

  const {
    mocapRecordingPath,
    isUsingManualPath,
    isLoading,
    setManualRecordingPath,
    clearManualRecordingPath,
    validateDirectory,
  } = useMocap();
  const { api, isElectron } = useElectronIPC();

  const handleSelectDirectory = async (): Promise<void> => {
    if (!isElectron || !api) return;
    try {
      const result: string | null = await api.fileSystem.selectDirectory.mutate();
      if (result) await setManualRecordingPath(result);
    } catch (error) {
      console.error("Failed to select directory:", error);
    }
  };

  const handleOpenFolder = async (): Promise<void> => {
    if (!isElectron || !api || !mocapRecordingPath) return;
    try {
      await api.fileSystem.openFolder.mutate({ path: mocapRecordingPath });
    } catch (error) {
      console.error("Failed to open folder:", error);
    }
  };

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
          <SubactionHeader text="Process Directory" />
        </div>

        {/* Process directory selector */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <button
            className="select-path button sm bg-middark br-1 border-1 border-black flex items-center gap-1 text-left flex-1"
            onClick={handleSelectDirectory}
            title="Click to select Process directory"
            disabled={!isElectron}
            style={{ minWidth: 0, overflow: "hidden" }}
          >
            {mocapRecordingPath ? (
              <p
                className="recording-path-preview flex-1 text md"
                style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              >
                {mocapRecordingPath}
              </p>
            ) : (
              <p
                className="text-gray flex-1 text md"
                style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
              >
                Select a folder where the mocap process will be saved.
              </p>
            )}
          </button>
          <div className="flex flex-row gap-1" style={{ flexShrink: 0 }}>
            {isUsingManualPath && (
              <IconButton
                icon="clear-icon"
                onClick={clearManualRecordingPath}
                title="Clear manual path (revert to default)"
              />
            )}
            <IconButton
              icon="save-icon"
              onClick={() => mocapRecordingPath && validateDirectory(mocapRecordingPath)}
              disabled={!mocapRecordingPath || isLoading}
              title="Re-check folder"
            />
            <IconButton
              icon="streaming-icon"
              onClick={handleOpenFolder}
              disabled={!isElectron || !mocapRecordingPath}
              title="Open folder in file explorer"
            />
          </div>
        </div>
        <p className="text sm text-gray">
          {isUsingManualPath ? "Using custom path" : "Using default recording directory"}
        </p>
      </div>
    </div>
  );
};

export default ProcessDirectoryModule;
