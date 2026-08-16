import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import ValueSelector from "@/components/ui-components/ValueSelector";
import IconButton from "@/components/ui-components/IconButton";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";
import { useCalibration } from "@/hooks/useCalibration";
import { CalibrationSolverMethod } from "@/store/slices/calibration";
import PromptTooltip from "@/components/ui-components/PromptTooltip";
import charucoSettingsImage from "@/assets/images/charuco_settings.webp";
import { useTranslation } from "react-i18next";

type BoardPreset = "5 x 3" | "7 x 5" | "Custom";

interface BoardPresetDims {
  squares_x: number;
  squares_y: number;
}

const BOARD_PRESETS: Record<Exclude<BoardPreset, "Custom">, BoardPresetDims> = {
  "5 x 3": { squares_x: 5, squares_y: 3 },
  "7 x 5": { squares_x: 7, squares_y: 5 },
};

interface CalibrationSettingsProps {
  onClose?: () => void;
}

const CalibrationSettings = ({ onClose }: CalibrationSettingsProps) => {
  const { t } = useTranslation();
  const modalRef = useRef<HTMLDivElement>(null);
  const { config, updateCalibrationConfig, pyceresAvailable } = useCalibration();
  const board = config.charucoBoard;

  const customPresetLabel = t("calibration.customPreset");
  const solverLabelToMethod = useMemo<Record<string, CalibrationSolverMethod>>(
    () => ({
      [t("calibration.aniposeLegacy")]: "anipose",
      [t("calibration.accurate")]: "pyceres",
    }),
    [t],
  );
  const solverMethodToLabel = useMemo<Record<CalibrationSolverMethod, string>>(
    () => ({
      anipose: t("calibration.aniposeLegacy"),
      pyceres: t("calibration.accurate"),
    }),
    [t],
  );
  const solverOptions = useMemo(() => {
    const options = [t("calibration.aniposeLegacy"), t("calibration.accurate")];
    return pyceresAvailable === false ? options.slice(0, 1) : options;
  }, [pyceresAvailable, t]);

  const handleClose = useCallback(() => {
    if (onClose) onClose();
  }, [onClose]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        modalRef.current &&
        !modalRef.current.contains(event.target as Node)
      ) {
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
      if (
        dims.squares_x === board.squares_x &&
        dims.squares_y === board.squares_y
      ) {
        return preset as BoardPreset;
      }
    }
    return "Custom";
  }, [board.squares_x, board.squares_y]);

  const [forcedCustom, setForcedCustom] = useState(false);
  const [showTooltip, setShowTooltip] = useState(() => {
    return !localStorage.getItem("calibration:onboarding:dismissed");
  });

  const closeTooltip = useCallback(() => {
    setShowTooltip(false);
    localStorage.setItem("calibration:onboarding:dismissed", "true");
  }, []);

  const toggleTooltip = useCallback(() => {
    setShowTooltip((prev) => {
      const next = !prev;
      if (next) {
        // User is opening it manually — remove dismissed flag so closing will re-dismiss
        localStorage.removeItem("calibration:onboarding:dismissed");
      }
      return next;
    });
  }, []);

  const displayedPreset: BoardPreset = forcedCustom ? "Custom" : currentPreset;

  const handlePresetChange = useCallback(
    (value: string) => {
      const preset: BoardPreset = value === customPresetLabel ? "Custom" : value as BoardPreset;
      if (preset === "Custom") {
        setForcedCustom(true);
        return;
      }
      setForcedCustom(false);
      updateCalibrationConfig({
        charucoBoard: { ...board, ...BOARD_PRESETS[preset] },
      });
    },
    [board, updateCalibrationConfig, customPresetLabel],
  );

  const handleSolverChange = useCallback(
    (value: string) => {
      const method = solverLabelToMethod[value];
      if (method) updateCalibrationConfig({ solverMethod: method });
    },
    [updateCalibrationConfig],
  );

  return (
    <div className="z-10 calibration-settings-flyout pos-fixed draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1">
      <div
        className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1"
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}

        <div className="flex flex-row justify-content-space-between items-center">
          <div className="flex flex-row flex-1 justify-content-space-between items-center w-100">
            <SubactionHeader text={t("calibration.charucoBoardSettings")} />
            <div
              data-onboarding="calibration:charuco-settings"
              className="flex flex-row pos-rel gap-1 items-center"
            >
              <IconButton
                icon="explainer-icon"
                className="button sm"
                onClick={toggleTooltip}
                tooltip
                tooltipText={t("calibration.learnAboutCharuco")}
                tooltipPosition="pos-left"
              />
              <PromptTooltip
                show={showTooltip}
                title={t("calibration.understandBoardSettings")}
                text={t("calibration.boardSettingsHelp")}
                image={true}
                imageSrc={charucoSettingsImage}
                position="pos-right"
                variant="default"
                onClose={closeTooltip}
              />
            </div>
          </div>
        </div>

        {/* Preset dropdown */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">{t("calibration.preset")}</span>
          <NameDropdownSelector
            key={displayedPreset}
            options={["5 x 3", "7 x 5", customPresetLabel]}
            initialValue={displayedPreset === "Custom" ? customPresetLabel : displayedPreset}
            onChange={handlePresetChange}
            className="flex flex-row"
          />
        </div>

        {/* X Square Size */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">{t("calibration.xSquareSize")}</span>
          <ValueSelector
            value={board.squares_x}
            min={2}
            max={20}
            step={1}
            unit=""
            disabled={displayedPreset !== "Custom"}
            onChange={(v) =>
              updateCalibrationConfig({
                charucoBoard: { ...board, squares_x: v },
              })
            }
          />
        </div>

        {/* Y Square Size */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">{t("calibration.ySquareSize")}</span>
          <ValueSelector
            value={board.squares_y}
            min={2}
            max={20}
            step={1}
            unit=""
            disabled={displayedPreset !== "Custom"}
            onChange={(v) =>
              updateCalibrationConfig({
                charucoBoard: { ...board, squares_y: v },
              })
            }
          />
        </div>

        <SubactionHeader text={t("calibration.boardDimensions")} />

        {/* Square length */}
        <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
          <span className="text-sm">{t("calibration.squareLength")}</span>
          <ValueSelector
            value={board.square_length_mm}
            min={1}
            max={9999999}
            step={0.1}
            unit="mm"
            onChange={(v) =>
              updateCalibrationConfig({
                charucoBoard: { ...board, square_length_mm: v },
              })
            }
          />
        </div>

        <SubactionHeader text={t("calibration.solverSettings")} />

        {/* Method dropdown (only shown when there's a choice to make) */}
        {solverOptions.length > 1 ? (
          <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
            <span className="text-sm">{t("calibration.method")}</span>
            <NameDropdownSelector
              key={config.solverMethod}
              options={solverOptions}
              initialValue={solverMethodToLabel[config.solverMethod]}
              onChange={handleSolverChange}
              className="flex flex-row"
            />
          </div>
        ) : (
          <div className="flex p-1 flex-row gap-1 items-center justify-content-space-between">
            <span className="text-sm">{t("calibration.method")}</span>
            <span className="text-sm">{solverMethodToLabel[config.solverMethod]}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default CalibrationSettings;
