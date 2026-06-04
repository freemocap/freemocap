import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import NameDropdownSelector from "@/components/ui-components/NameDropdownSelector";
import ButtonSm from "@/components/ui-components/ButtonSm";
import { serverUrls } from "@/services";
import { backendFetch } from '@/services/electron-ipc/backend-fetch';

type MicrophoneSelectorProps = {
    selectedMicIndex: number;
    onMicSelected: (micIndex: number) => void;
    disabled: boolean;
};

type MicrophoneMap = Record<number, string>;

const NO_MIC_LABEL = "No microphone";

export const MicrophoneSelector: React.FC<MicrophoneSelectorProps> = ({
    selectedMicIndex, onMicSelected, disabled,
}) => {
    const [microphones, setMicrophones] = useState<MicrophoneMap>({});
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const { t } = useTranslation();

    const detectMicrophones = async (): Promise<void> => {
        setLoading(true);
        setError(null);
        try {
            const response = await backendFetch(serverUrls.endpoints.detectMicrophones);
            if (!response.ok) throw new Error(`Failed: ${response.statusText}`);
            const data = await response.json();
            setMicrophones(data.microphones ?? {});
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            setError(msg);
            console.error("Microphone detection failed:", msg);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { detectMicrophones(); }, []);

    const micEntries = Object.entries(microphones).map(([id, name]) => ({
        id: Number(id), name: name as string,
    }));

    const options = [NO_MIC_LABEL, ...micEntries.map(m => m.name)];
    const selectedName = selectedMicIndex >= 0
        ? (micEntries.find(m => m.id === selectedMicIndex)?.name ?? NO_MIC_LABEL)
        : NO_MIC_LABEL;

    const handleChange = (name: string) => {
        if (name === NO_MIC_LABEL) { onMicSelected(-1); return; }
        const mic = micEntries.find(m => m.name === name);
        if (mic) onMicSelected(mic.id);
    };

    return (
        <div className="microphone-selector-group flex flex-col gap-1">
            <div className="flex items-center gap-1">
                <span className={clsx("icon icon-size-20", selectedMicIndex >= 0 ? "mic-active-icon" : "mic-icon")} />
                <div className={clsx("flex-1", (disabled || loading) && "disabled")}>
                    <NameDropdownSelector
                        options={options}
                        initialValue={selectedName}
                        onChange={handleChange}
                    />
                </div>
                <ButtonSm
                    iconClass={loading ? "loader-icon" : "rotate-icon"}
                    text=""
                    textColor="text-gray"
                    onClick={detectMicrophones}
                    buttonType={disabled || loading ? "disabled" : ""}
                    title={t("refreshMicrophoneList")}

                    tooltip={true}
                    tooltipPosition="pos-left"
                    tooltipText={t("refreshMicrophoneList")}
                />
            </div>
            {error && (
                <p className="error-message text sm text-error text-nowrap overflow-hidden" style={{ textOverflow: 'ellipsis' }} title={error}>
                    {error}
                </p>
            )}
        </div>
    );
};
