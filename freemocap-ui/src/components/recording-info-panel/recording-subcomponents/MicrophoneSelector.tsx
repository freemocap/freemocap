import React, {useEffect, useState} from "react";
import { useTranslation } from "react-i18next";
import {
    Box,
    FormControl,
    IconButton,
    MenuItem,
    Select,
    Tooltip,
    Typography,
} from "@mui/material";
import {Mic, MicOff, Refresh} from "@mui/icons-material";
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
            const response = await fetch(useAppUrls.getHttpEndpointUrls.detectMicrophones);
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
        <Box sx={{display: "flex", alignItems: "center", gap: 0.5, minWidth: 0}}>
            <Tooltip title={isActive ? t("audioRecordingEnabled") : t("noMicrophoneSelected")}>
                {isActive ? (
                    <Mic sx={{fontSize: 16, color: "success.main", flexShrink: 0}}/>
                ) : (
                    <MicOff sx={{fontSize: 16, color: "text.disabled", flexShrink: 0}}/>
                )}
            </Tooltip>

            <FormControl size="small" sx={{minWidth: 120, flex: 1}} disabled={disabled || loading}>
                <Select
                    value={selectedMicIndex}
                    onChange={(e) => onMicSelected(Number(e.target.value))}
                    displayEmpty
                    sx={{
                        fontSize: "0.75rem",
                        height: 28,
                        "& .MuiSelect-select": {py: 0.25},
                    }}
                >
                    <MenuItem value={-1}>
                        <Typography variant="caption" color="text.secondary">
                            {t('noMicrophone')}
                        </Typography>
                    </MenuItem>
                    {micEntries.map(({id, name}) => (
                        <MenuItem key={id} value={id}>
                            <Typography variant="caption" noWrap>
                                {name}
                            </Typography>
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            <Tooltip title={t("refreshMicrophoneList")}>
                <span>
                    <IconButton
                        size="small"
                        onClick={detectMicrophones}
                        disabled={disabled || loading}
                        sx={{p: 0.25, flexShrink: 0}}
                    >
                        <Refresh sx={{fontSize: 14}}/>
                    </IconButton>
                </span>
            </Tooltip>

            {error && (
                <Typography variant="caption" color="error" noWrap sx={{fontSize: "0.65rem"}}>
                    {error}
                </Typography>
            )}
        </Box>
    );
};
