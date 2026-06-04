import React, {useEffect, useState} from "react";
import {useTranslation} from "react-i18next";
import {serverUrls} from "@/services";

type MicrophoneSelectorProps = {
    selectedMicIndex: number;
    onMicSelected: (micIndex: number) => void;
    disabled: boolean;
};

type MicrophoneMap = Record<number, string>;

export const MicrophoneSelector: React.FC<MicrophoneSelectorProps> = ({
    selectedMicIndex,
    onMicSelected,
    disabled,
}) => {
    const [microphones, setMicrophones] = useState<MicrophoneMap>({});
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const { t } = useTranslation();

    const detectMicrophones = async (): Promise<void> => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(serverUrls.endpoints.detectMicrophones);
            if (!response.ok) {
                throw new Error(`Failed to detect microphones: ${response.statusText}`);
            }
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

    // Detect on mount
    useEffect(() => {
        detectMicrophones();
    }, []);

    const micEntries = Object.entries(microphones).map(([id, name]) => ({
        id: Number(id),
        name: name as string,
    }));

    const isActive = selectedMicIndex >= 0;

    return (
        <div className="flex flex-row items-center gap-1" style={{minWidth: 0}}>
            <span
                className="icon icon-size-20"
                title={isActive ? t("audioRecordingEnabled") : t("noMicrophoneSelected")}
                style={{
                    flexShrink: 0,
                    color: isActive ? 'var(--color-success)' : 'var(--color-text-disabled)',
                    fontSize: 16,
                }}
            >
                {isActive ? '🎤' : '🔇'}
            </span>

            <select
                className="input-field text md"
                value={selectedMicIndex}
                onChange={(e) => onMicSelected(Number(e.target.value))}
                disabled={disabled || loading}
                style={{fontSize: '0.75rem', height: 28, flex: 1, minWidth: 120}}
            >
                <option value={-1}>{t('noMicrophone')}</option>
                {micEntries.map(({id, name}) => (
                    <option key={id} value={id}>{name}</option>
                ))}
            </select>

            <button
                className="button icon-button br-1"
                onClick={detectMicrophones}
                disabled={disabled || loading}
                title={t("refreshMicrophoneList")}
                style={{flexShrink: 0}}
            >
                <span className="icon save-icon icon-size-12" />
            </button>

            {error && (
                <p className="text sm text-error text-nowrap" style={{fontSize: '0.65rem'}}>
                    {error}
                </p>
            )}
        </div>
    );
};
