import React, { useEffect, useRef } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import { useMocap } from "@/hooks/useMocap";
import { useElectronIPC } from "@/services";
import { useTranslation } from "react-i18next";

interface ProcessDirectoryModuleProps {
  open: boolean;
  onClose: () => void;
}

const ProcessDirectoryModule: React.FC<ProcessDirectoryModuleProps> = ({
  open,
  onClose,
}) => {
  const { t } = useTranslation();
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
      const result: string | null = await api.fileSystem.selectDirectory.mutate({
        defaultPath: mocapRecordingPath || undefined,
      });
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
          <SubactionHeader text={t("mocap.processingDirectory")} />
        </div>

        {/* Process directory selector */}
        <div className="set-mocap-directory flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="icon icon-size-20 subcat-icon"></span>
          <button
            className="select-path button sm bg-middark br-1 border-1 border-black flex items-center gap-1 text-left flex-1"
            onClick={handleSelectDirectory}
            title={t("mocap.selectDirectory")}
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
                {t("mocap.selectProcessingFolderHelp")}
              </p>
            )}
          </button>
          <div className="flex flex-row gap-1" style={{ flexShrink: 0 }}>
            {isUsingManualPath && (
              <IconButton
                icon="clear-icon"
                onClick={clearManualRecordingPath}
                title={t("mocap.clearManualPath")}
                tooltip={true}
                tooltipPosition="pos-top-right"
                tooltipText={t("mocap.clearManualPath")}
              />
            )}
            <IconButton
              icon="checkUpdate-icon"
              onClick={() => mocapRecordingPath && validateDirectory(mocapRecordingPath)}
              disabled={!mocapRecordingPath || isLoading}
              title={t("mocap.recheckFolder")}
              tooltip={true}
              tooltipPosition="pos-top-right"
              tooltipText={t("mocap.recheckFolder")}
            />
            <IconButton
              icon="subfolder-icon"
              onClick={handleOpenFolder}
              disabled={!isElectron || !mocapRecordingPath}
              title={t("mocap.openFolderInExplorer")}
              tooltip={true}
              tooltipPosition="pos-top-right"
              tooltipText={t("mocap.openFolderInExplorer")}
            />
          </div>
        </div>
        <p className="text sm text-gray p-1">
          {isUsingManualPath ? t("mocap.usingCustomPath") : t("mocap.usingDefaultDirectory")}
        </p>
      </div>
    </div>
  );
};

export default ProcessDirectoryModule;
