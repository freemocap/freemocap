import React, { useCallback, useEffect, useRef } from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";
import { useMocap } from "@/hooks/useMocap";
import { useRealtimePipelineSync } from "@/hooks/useRealtimePipelineSync";
import {
  DEFAULT_REALTIME_FILTER_CONFIG,
  RealtimeFilterConfig,
} from "@/store/slices/mocap";
import IconButton from "@/components/ui-components/IconButton";
interface MOCAPthreeDReconstructionSettingsProps {
  open: boolean;
  onClose: () => void;
}

const MOCAPthreeDReconstructionSettings: React.FC<
  MOCAPthreeDReconstructionSettingsProps
> = ({ open, onClose }) => {
  const modalRef = useRef<HTMLDivElement>(null);

  const {
    skeletonFilterConfig,
    updateSkeletonFilterConfigLocalOnly,
    replaceSkeletonFilterConfigLocalOnly,
    isLoading,
  } = useMocap();
  const {
    triggerRealtimeApply,
    applyOrUpdatePipelineConfig,
    pipelineConfig,
    aggregatorConfig,
  } = useRealtimePipelineSync();

  const handleUpdateSkeletonFilterConfig = useCallback(
    (updates: Partial<RealtimeFilterConfig>) => {
      updateSkeletonFilterConfigLocalOnly(updates);
      triggerRealtimeApply();
    },
    [updateSkeletonFilterConfigLocalOnly, triggerRealtimeApply],
  );

  const handleResetDefaults = useCallback(() => {
    replaceSkeletonFilterConfigLocalOnly({ ...DEFAULT_REALTIME_FILTER_CONFIG });
    triggerRealtimeApply();
  }, [replaceSkeletonFilterConfigLocalOnly, triggerRealtimeApply]);

  const handleSkeletonToggle = useCallback(
    (value: boolean) =>
      applyOrUpdatePipelineConfig({
        ...pipelineConfig,
        aggregator_config: { ...aggregatorConfig, skeleton_enabled: value },
      }),
    [applyOrUpdatePipelineConfig, pipelineConfig, aggregatorConfig],
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
          <SubactionHeader text="Point Gate settings" />
          <div className="flex flex-row gap-1 items-center">
            <IconButton
              icon="clear-icon"
              className="button sm"
              onClick={handleResetDefaults}
              disabled={isLoading}
              tooltip
              tooltipText="Reset to defaults"
              tooltipPosition="pos-left"
            />

            {/* <IconButton
              icon="close-icon"
              className="button sm"
              onClick={onClose}
            /> */}
          </div>
        </div>

        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max Reproj Error</span>

          <ValueSelector
            value={skeletonFilterConfig.max_reprojection_error_px}
            min={5}
            max={200}
            step={1}
            unit="px"
            onChange={(v) =>
              handleUpdateSkeletonFilterConfig({ max_reprojection_error_px: v })
            }
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max Velocity</span>

          <ValueSelector
            value={skeletonFilterConfig.max_velocity_m_per_s}
            min={5}
            max={200}
            step={1}
            unit="m/s"
            onChange={(v) =>
              handleUpdateSkeletonFilterConfig({ max_velocity_m_per_s: v })
            }
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max Rejected streaks</span>

          <ValueSelector
            value={skeletonFilterConfig.max_rejected_streak}
            min={1}
            max={30}
            step={1}
            unit=""
            onChange={(v) =>
              handleUpdateSkeletonFilterConfig({ max_rejected_streak: v })
            }
          />
        </div>

        <SubactionHeader text="One Euro Filter" />
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Min Cutoff</span>
          <ValueSelector
            value={skeletonFilterConfig.min_cutoff}
            min={0.0001}
            max={0.1}
            step={0.0005}
            unit=""
            onChange={(v) =>
              handleUpdateSkeletonFilterConfig({ min_cutoff: v })
            }
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Beta</span>
          <ValueSelector
            value={skeletonFilterConfig.beta}
            min={0}
            max={5}
            step={0.05}
            unit=""
            onChange={(v) => handleUpdateSkeletonFilterConfig({ beta: v })}
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">D Cutoff</span>
          <ValueSelector
            value={skeletonFilterConfig.d_cutoff}
            min={0.1}
            max={5}
            step={0.1}
            unit=""
            onChange={(v) => handleUpdateSkeletonFilterConfig({ d_cutoff: v })}
          />
        </div>

        <SubactionHeader text="Fabrik" />
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Max iterations</span>
          <ValueSelector
            value={skeletonFilterConfig.fabrik_max_iterations}
            min={1}
            max={100}
            step={1}
            unit=""
            onChange={(v) =>
              handleUpdateSkeletonFilterConfig({ fabrik_max_iterations: v })
            }
          />
        </div>

        <SubactionHeader text="Body Model" />
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Height</span>
          <ValueSelector
            value={skeletonFilterConfig.height_meters}
            min={0.5}
            max={3.0}
            step={0.01}
            unit="m"
            onChange={(v) =>
              handleUpdateSkeletonFilterConfig({ height_meters: v })
            }
          />
        </div>
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">Noise sigma</span>
          <ValueSelector
            value={skeletonFilterConfig.noise_sigma}
            min={0.001}
            max={0.05}
            step={0.001}
            unit="m"
            onChange={(v) =>
              handleUpdateSkeletonFilterConfig({ noise_sigma: v })
            }
          />
        </div>

        <ToggleComponent
          text="Skeleton"
          isToggled={aggregatorConfig.skeleton_enabled}
          onToggle={handleSkeletonToggle}
          disabled={isLoading}
        />
      </div>
    </div>
  );
};

export default MOCAPthreeDReconstructionSettings;
