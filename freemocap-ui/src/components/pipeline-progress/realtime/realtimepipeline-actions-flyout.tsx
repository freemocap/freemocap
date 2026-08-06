import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import ButtonSm from "@/components/ui-components/ButtonSm";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import { useRealtimePipelineSync } from "@/hooks/useRealtimePipelineSync";
import { openPipelineMetricsWindow } from "@/services/electron-ipc/open-pipeline-metrics-window";
import { serverUrls } from "@/constants/server-urls";

interface GpuInfo {
    gpus: {name: string; vram_gb: string | null}[];
    onnx_version: string | null;
    onnx_providers: string[];
    gpu_acceleration_available: boolean;
    optimal_provider: string;
}

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

    const [gpuInfo, setGpuInfo] = useState<GpuInfo | null>(null);

    useEffect(() => {
        fetch(serverUrls.endpoints.gpuInfo)
            .then(r => r.json())
            .then(setGpuInfo)
            .catch(() => {});
    }, []);

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

                {gpuInfo && (
                    <div className="text sm" style={{padding: '8px 0', color: 'var(--gray-400)', borderTop: '1px solid var(--gray-700)', marginTop: 4}}>
                        <div style={{marginBottom: 2}}>
                            <strong>{gpuInfo.gpus.length > 0 ? gpuInfo.gpus[0].name : 'No GPU detected'}</strong>
                            {gpuInfo.gpus[0]?.vram_gb && <span> · {gpuInfo.gpus[0].vram_gb}</span>}
                        </div>
                        <div style={{marginBottom: 2}}>
                            Providers: {gpuInfo.onnx_providers.length > 0 ? gpuInfo.onnx_providers.join(', ') : 'None'}
                        </div>
                        <div>
                            Optimal: {gpuInfo.optimal_provider.replace('ExecutionProvider', '')}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default RTPPipelineActionsFlyout;
