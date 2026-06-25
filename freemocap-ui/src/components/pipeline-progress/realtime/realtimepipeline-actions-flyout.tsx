import React, { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import ButtonSm from "@/components/ui-components/ButtonSm";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import { useRealtimePipelineSync } from "@/hooks/useRealtimePipelineSync";
import { openPipelineMetricsWindow } from "@/services/electron-ipc/open-pipeline-metrics-window";

interface RTPPipelineActionsFlyoutProps {
    open: boolean;
    onClose: () => void;
}

const RTPPipelineActionsFlyout: React.FC<RTPPipelineActionsFlyoutProps> = ({
    open,
    onClose,
}) => {
    const { t } = useTranslation();
    const modalRef = useRef<HTMLDivElement>(null);
    const {
        pipelineConfig,
        applyOrUpdatePipelineConfig,
        isLoading,
    } = useRealtimePipelineSync();

    const logPipelineTimes = pipelineConfig.log_pipeline_times !== false;

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

    const handleOpenPipelineMetrics = (): void => {
        void openPipelineMetricsWindow();
        onClose();
    };

    const handleLogPipelineTimesToggle = (checked: boolean): void => {
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            log_pipeline_times: checked,
        });
    };

    return (
        <div
            ref={modalRef}
            className="RTP-settings-flyout pos-abs top-5 right-0 draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
        >
            <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1">
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text={t("pipelineActions")} />
                    <IconButton icon="close-icon" className="button sm" onClick={onClose} />
                </div>

                <ButtonSm
                    text={t("openPipelineMetricsWindow")}
                    iconClass="externallink-icon"
                    onClick={handleOpenPipelineMetrics}
                    className="secondary w-full"
                />

                <ToggleComponent
                    text={t("logPipelineTimes")}
                    isToggled={logPipelineTimes}
                    onToggle={handleLogPipelineTimesToggle}
                    disabled={isLoading}
                />
            </div>
        </div>
    );
};

export default RTPPipelineActionsFlyout;
