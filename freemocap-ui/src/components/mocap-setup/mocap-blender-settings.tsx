import React, { useEffect, useRef } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ButtonSm from "@/components/ui-components/ButtonSm";
import { useMocap } from "@/hooks/useMocap";
import { useBlender } from "@/hooks/useBlender";
import { useElectronIPC } from "@/services";
import { useTranslation } from "react-i18next";

interface MOCAPBlenderSettingsProps {
  open: boolean;
  onClose: () => void;
}

const MOCAPBlenderSettings: React.FC<MOCAPBlenderSettingsProps> = ({
  open,
  onClose,
}) => {
  const { t } = useTranslation();
  const modalRef = useRef<HTMLDivElement>(null);

  const { mocapRecordingPath, detectorType } = useMocap();
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

  // The freemocap_blender_addon only understands MediaPipe output so far -
  // an rtmpose recording's Blender export is turned off client-side to match.
  const blenderSupported = detectorType === "mediapipe";

  const canExport =
    blenderSupported &&
    !!mocapRecordingPath &&
    !!effectiveBlenderExePath &&
    !isExporting;

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
          <SubactionHeader text={t("blender.settings")} />
        </div>
        <div className="flex flex-row justify-content-space-between items-center">
          <div className="flex flex-row items-center">
            <span className="icon icon-size-20 blender-icon"></span>
            <p className="p-1 text-gray">{t("blender.executable")}</p>
          </div>
        <ButtonSm
            text={isDetecting ? t("blender.detecting") : t("blender.autodetect")}
            onClick={redetectBlender}
            disabled={isDetecting}
            tooltip={true}
            tooltipPosition="pos-top-right"
            tooltipText={t("blender.autodetectHelp")}
          />
        </div>

        {/* Blender executable selector */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <button
            className="select-path button sm bg-middark br-1 border-1 border-black flex items-center gap-1 text-left flex-1"
            onClick={handleSelectBlenderExe}
            title={t("blender.selectExecutableHelp")}
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
                {isDetecting ? t("blender.detecting") : t("blender.selectExecutable")}
              </p>
            )}
          </button>
        </div>
        <p className="text sm text-gray p-1 mb-3">
          {isUsingManualBlenderPath
            ? t("blender.usingManual")
            : effectiveBlenderExePath
              ? t("blender.autoDetected")
              : t("blender.browseHint")}
        </p>

        {!blenderSupported && (
          <p className="text sm text-gray p-1">
            {t("blender.mediapipeOnly")}
          </p>
        )}

        {/* Toggles */}
        <ToggleComponent
          text={t("blender.exportAfterProcessing")}
          isToggled={exportToBlenderEnabled && blenderSupported}
          onToggle={setExportToBlenderEnabled}
          disabled={!blenderSupported}
        />

        <ToggleComponent
          text={t("blender.autoOpenBlend")}
          isToggled={autoOpenBlendFile && blenderSupported}
          onToggle={setAutoOpenBlendFile}
          disabled={!blenderSupported || !exportToBlenderEnabled}
        />

        <ButtonSm
          text={isExporting ? t("blender.exporting") : t("blender.processRecording")}
          onClick={handleProcessWithBlender}
          disabled={!canExport}
          className="full-width quaternary mt-3"
          tooltip={true}
          tooltipPosition="pos-bottom-left"
          tooltipText={
            blenderSupported
              ? t("blender.processHelp")
              : t("blender.mediapipeOnlyShort")
          }
        />

        <ButtonSm
          text={isOpening ? t("blender.opening") : t("blender.openBlend")}
          onClick={handleOpenInBlender}
          disabled={!canOpen}
          className="full-width quaternary"
          tooltip={true}
          tooltipPosition="pos-bottom-left"
          tooltipText={t("blender.openBlendHelp")}
        />

        {lastBlendFilePath && (
          <p className="text sm text-gray p-1 mb-3">
            {t("blender.lastExport")} {lastBlendFilePath}
          </p>
        )}
      </div>
    </div>
  );
};

export default MOCAPBlenderSettings;
