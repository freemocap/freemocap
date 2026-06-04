import React, {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';

interface StartStopButtonProps {
    isRecording: boolean;
    isPending: boolean;
    countdown: number | null;
    recordingStartTime: number | null;
    disabled: boolean;
    onClick: () => void;
}

const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    const parts: string[] = [];
    if (hours > 0) {
        parts.push(hours.toString().padStart(2, '0'));
    }
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(secs.toString().padStart(2, '0'));

    return parts.join(':');
};

export const StartStopRecordingButton: React.FC<StartStopButtonProps> = ({
    isRecording,
    isPending,
    countdown,
    recordingStartTime,
    disabled,
    onClick
}) => {
    const [recordingDuration, setRecordingDuration] = useState<number>(0);
    const { t } = useTranslation();

    // Update recording duration every second
    useEffect(() => {
        if (!isRecording || !recordingStartTime || isPending) {
            setRecordingDuration(0);
            return;
        }

        const updateDuration = (): void => {
            const now = Date.now();
            const duration = Math.floor((now - recordingStartTime) / 1000);
            setRecordingDuration(duration);
        };

        // Update immediately
        updateDuration();

        // Then update every second
        const interval = setInterval(updateDuration, 1000);

        return () => clearInterval(interval);
    }, [isRecording, recordingStartTime, isPending]);

    const getButtonContent = (): React.ReactNode => {
        // Show countdown if active
        if (countdown !== null && countdown > 0) {
            return (
                <div className="flex flex-row items-center gap-1">
                    <p className="text bg text-white">
                        {t('startingIn', { countdown })}
                    </p>
                </div>
            );
        }

        // Show pending state
        if (isPending) {
            return (
                <div className="flex flex-row items-center gap-1">
                    <span className="icon loader-icon icon-size-20" />
                    <p className="text bg text-white">
                        {isRecording ? t('stopping') : t('starting')}
                    </p>
                </div>
            );
        }

        // Show recording state with duration
        if (isRecording) {
            return (
                <div className="flex flex-col items-center">
                    <p className="text bg text-white">{t('stopRecordingButton')}</p>
                    <p className="text sm text-white" style={{fontSize: '0.9rem', fontFamily: 'monospace'}}>
                        {formatDuration(recordingDuration)}
                    </p>
                </div>
            );
        }

        // Default start state
        return (
            <p className="text bg text-white">{t('startRecordingButton')}</p>
        );
    };

    const buttonStyle: React.CSSProperties = {
        backgroundColor: isRecording ? '#8d0a02' : '#005d94',
        borderStyle: 'solid',
        borderWidth: '3px',
        borderColor: isPending ? '#ffa500' : '#ff55ff',
        padding: 10,
        position: 'relative',
        transition: 'all 0.3s ease',
        opacity: isPending ? 0.8 : 1,
        width: '100%',
        cursor: disabled || isPending || countdown !== null ? 'not-allowed' : 'pointer',
        ...(isRecording && !isPending
            ? {animation: 'pulseBg 3s infinite ease-in-out'}
            : {}),
    };

    return (
        <>
            <style>{`
                @keyframes pulseBg {
                    0%   { background-color: #fb1402; }
                    50%  { background-color: #711c1c; }
                    100% { background-color: #fb1402; }
                }
            `}</style>
            <button
                onClick={onClick}
                disabled={disabled || isPending || countdown !== null}
                style={buttonStyle}
                className="button sm"
            >
                {getButtonContent()}
            </button>
        </>
    );
};
