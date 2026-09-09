import React, { useEffect, useRef, useState } from "react";
import IconButton from "@/components/ui-components/IconButton";
import { useMocap } from "@/hooks/useMocap";
import { useElectronIPC } from "@/services";

interface RecordingDirectoryModuleProps {
  open: boolean;
  onClose: () => void;
}

const RecordingDirectoryModule: React.FC<RecordingDirectoryModuleProps> = ({
  open,
  onClose,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const [directoryError, setDirectoryError] = useState<string | null>(null);

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
    setDirectoryError(null);
    try {
      const result: string | null = await api.fileSystem.selectDirectory.mutate({
        defaultPath: mocapRecordingPath || undefined,
      });
      if (result) await setManualRecordingPath(result);
    } catch (error) {
      setDirectoryError(error instanceof Error ? error.message : String(error));
    }
  };

  const handleOpenFolder = async (): Promise<void> => {
    if (!isElectron || !api || !mocapRecordingPath) return;
    setDirectoryError(null);
    try {
      await api.fileSystem.openFolder.mutate({ path: mocapRecordingPath });
    } catch (error) {
      setDirectoryError(error instanceof Error ? error.message : String(error));
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
        {/* Recording directory selector */}
        <div className="set-mocap-directory flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="icon icon-size-20 subcat-icon"></span>
          <button
            className="select-path button sm bg-middark br-1 border-1 border-black flex items-center gap-1 text-left flex-1 min-w-0 overflow-hidden"
            onClick={mocapRecordingPath ? handleOpenFolder : handleSelectDirectory}
            title={mocapRecordingPath || "Select a recording directory"}
            aria-label={mocapRecordingPath ? `Open recording folder: ${mocapRecordingPath}` : "Choose recording folder"}
            disabled={!isElectron}

          >
            {mocapRecordingPath ? (
              <p
                className="recording-path-preview recording-path-tail flex-1 text md"
              >
                <bdi dir="ltr">{mocapRecordingPath}</bdi>
              </p>
            ) : (
              <p
                className="text-gray flex-1 text md truncate"
              >
                Select a folder where the mocap process will be saved.
              </p>
            )}
          </button>
          <div className="flex flex-row gap-1 flex-shrink-0">
            <IconButton
              icon="subfolder-icon"
              onClick={handleSelectDirectory}
              disabled={!isElectron}
              title="Choose a different recording folder"
            />
            {isUsingManualPath && (
              <IconButton
                icon="clear-icon"
                onClick={clearManualRecordingPath}
                title="Clear manual path (revert to default)"
                tooltip={true}
                tooltipPosition="pos-top-right"
                tooltipText="Clear manual path (revert to default)"
              />
            )}
            <IconButton
              icon="checkUpdate-icon"
              onClick={() => mocapRecordingPath && validateDirectory(mocapRecordingPath)}
              disabled={!mocapRecordingPath || isLoading}
              title="Re-check folder"
              tooltip={true}
              tooltipPosition="pos-top-right"
              tooltipText="Re-check folder"
            />
            <IconButton
              icon="subfolder-icon"
              onClick={handleOpenFolder}
              disabled={!isElectron || !mocapRecordingPath}
              title="Open folder in file explorer"
              tooltip={true}
              tooltipPosition="pos-top-right"
              tooltipText="Open folder in file explorer"
            />
          </div>
        </div>
        <p className="text sm text-gray p-1">
          {isUsingManualPath ? "Using custom path" : "Using default recording directory"}
        </p>
        {directoryError && <p role="alert" className="text sm text-error">{directoryError}</p>}
      </div>
    </div>
  );
};

export default RecordingDirectoryModule;

