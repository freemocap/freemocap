import React from "react";
import { useTranslation } from "react-i18next";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import ValueSelector from "@/components/ui-components/ValueSelector";

interface DelayStartControlProps {
  useDelay: boolean;
  delaySeconds: number;
  onDelayToggle: (checked: boolean) => void;
  onDelayChange: (seconds: number) => void;
}

export const DelayRecordingStartControl: React.FC<DelayStartControlProps> = ({
  useDelay,
  delaySeconds,
  onDelayToggle,
  onDelayChange,
}) => {
  const { t } = useTranslation();
  return (
    <div className="delay-recording flex items-center gap-1 flex-wrap align-end flex-end">
      <ToggleComponent
        text={t("delayStart")}
        isToggled={useDelay}
        onToggle={onDelayToggle}
      />
      <div className="w-full flex items-center gap-1 flex-wrap justify-content-space-between">
   
         {useDelay && (
          <div className="flex flex-row justify-content-space-between items-center w-full px-2">
            <div className="flex items-center gap-1 flex-wrap">
              <span className="icon icon-size-20 subcat-icon"></span>
              <p className="text-left text-white">{t("StartAfter")}</p>
            </div>
            <ValueSelector
              value={delaySeconds}
              min={1}
              max={60}
              unit="s"
              onChange={onDelayChange}
            />
          </div>
        )}
      </div>
    </div>
  );
};
