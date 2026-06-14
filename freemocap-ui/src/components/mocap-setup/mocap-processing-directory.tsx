import React, { useCallback, useEffect, useRef, useState } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";
import ButtonSm from "@/components/ui-components/ButtonSm";
import { useMocap } from "@/hooks/useMocap";
import { useRealtimePipelineSync } from "@/hooks/useRealtimePipelineSync";
import { useElectronIPC } from "@/services";
import {
  detectPreset,
  MEDIAPIPE_POSTHOC_PRESET,
  MEDIAPIPE_REALTIME_PRESET,
  MediapipeDetectorConfig,
} from "@/store/slices/mocap";

interface ProcessDirectoryModuleProps {
  open: boolean;
  onClose: () => void;
}
const PRESET_OPTIONS = ["Lite (Fastest)", "PostHog (Accurate)", "Custom"];

const presetLabelToTarget: Record<string, "realtime" | "posthoc"> = {
  "Lite (Fastest)": "realtime",
  "PostHog (Accurate)": "posthoc",
};

const presetValueToLabel: Record<string, string> = {
  realtime: "Lite (Fastest)",
  posthoc: "PostHog (Accurate)",
  custom: "Custom",
};

const ProcessDirectoryModule: React.FC<ProcessDirectoryModuleProps> = ({
  open,
  onClose,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const [processDirectory, setprocessDirectory] = useState<string>("");

  const {
    detectorConfig,
    updateDetectorConfigLocalOnly,
    replaceDetectorConfigLocalOnly,
    isLoading,
  } = useMocap();
  const { triggerRealtimeApply } = useRealtimePipelineSync();
  const { api, isElectron } = useElectronIPC();

  const handleSelectDirectory = async (): Promise<void> => {
    if (!isElectron || !api) return;
    try {
      const result: string | null = await api.fileSystem.selectDirectory.mutate();
      if (result) setprocessDirectory(result);
    } catch (error) {
      console.error("Failed to select directory:", error);
    }
  };

  const handleUpdateDetectorConfig = useCallback(
    (updates: Partial<MediapipeDetectorConfig>) => {
      updateDetectorConfigLocalOnly(updates);
      triggerRealtimeApply();
    },
    [updateDetectorConfigLocalOnly, triggerRealtimeApply],
  );

  const handleReplaceDetectorConfig = useCallback(
    (config: MediapipeDetectorConfig) => {
      replaceDetectorConfigLocalOnly(config);
      triggerRealtimeApply();
    },
    [replaceDetectorConfigLocalOnly, triggerRealtimeApply],
  );

  const currentPreset = detectPreset(detectorConfig);

  const handlePresetChange = useCallback(
    (label: string) => {
      const target = presetLabelToTarget[label];
      if (target === "realtime")
        handleReplaceDetectorConfig({ ...MEDIAPIPE_REALTIME_PRESET });
      else if (target === "posthoc")
        handleReplaceDetectorConfig({ ...MEDIAPIPE_POSTHOC_PRESET });
    },
    [handleReplaceDetectorConfig],
  );

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
          {/* <IconButton icon="close-icon" onClick={onClose} /> */}
        </div>
        <div className="flex flex-row justify-content-space-between items-center">
                  <ToggleComponent
          text="Use a custom directory for mocap process"
          isToggled={detectorConfig.autoopen_blen_file}
          onToggle={(checked) =>
            handleUpdateDetectorConfig({ autoopen_blen_file: checked })
          }
          disabled={isLoading}
        />
        </div>
        

        {/* Process directory selector */}
        <div className={`select-custom-mocap-directory flex p-1 flex-row gap-1 items-center justify-content-space-between${!detectorConfig.autoopen_blen_file ? " disabled" : ""}`}>
          <button
            className="select-path button sm bg-middark br-1 border-1 border-black flex items-center gap-1 text-left flex-1"
            onClick={handleSelectDirectory}
            title="Click to select Process directory"
            disabled={!isElectron}
          >
            {processDirectory ? (
              <p className="recording-path-preview flex text-wrap flex-1 text md">
                {processDirectory}
              </p>
            ) : (
              <p className="text-gray flex text-wrap flex-1 text md">
                Select a folder where the mocap process will be saved.
              </p>
            )}
          </button>
        </div>

        {/* Toggles */}




      </div>
    </div>
  );
};

export default ProcessDirectoryModule;
