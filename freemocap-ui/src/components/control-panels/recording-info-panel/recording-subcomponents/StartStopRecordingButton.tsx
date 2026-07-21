import React, {useEffect, useState} from 'react';
import clsx from 'clsx';
import {useTranslation} from 'react-i18next';

interface StartStopButtonProps {
    isRecording: boolean;
    isPending: boolean;
    countdown: number | null;
    recordingStartTime: number | null;
    disabled: boolean;
    onClick: () => void;
    tooltipText?: string;
}

const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    const parts: string[] = [];
    if (hours > 0) parts.push(hours.toString().padStart(2, '0'));
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(secs.toString().padStart(2, '0'));
    return parts.join(':');
};

export const StartStopRecordingButton: React.FC<StartStopButtonProps> = ({
    isRecording, isPending, countdown, recordingStartTime, disabled, onClick, tooltipText,
}) => {
    const [recordingDuration, setRecordingDuration] = useState<number>(0);
    const {t} = useTranslation();

    useEffect(() => {
        if (!isRecording || !recordingStartTime || isPending) {
            setRecordingDuration(0);
            return;
        }
        const update = () => setRecordingDuration(Math.floor((Date.now() - recordingStartTime) / 1000));
        update();
        const interval = setInterval(update, 1000);
        return () => clearInterval(interval);
    }, [isRecording, recordingStartTime, isPending]);

    const isDisabled = disabled || isPending;

    const buttonEl = (
        <button
            className={clsx(
                "accent text-nowrap flex flex-row flex-1 gap-1 br-1 button sm min-w-fit-content flex-inline text-left items-center full-width primary justify-center",
                isRecording ? "record-button-active" : isPending ? "record-button-pending" : "accent",
            )}
            onClick={onClick}
            disabled={isDisabled}
            style={isDisabled && tooltipText ? {pointerEvents: "none"} : undefined}
        >
            {countdown !== null && countdown > 0 ? (
                <div className="flex items-center gap-1">
                    <span className="icon loader-icon icon-size-20" />
                    <p className="text bg text-white">{t('startingIn', {countdown})}</p>
                </div>
            ) : isPending ? (
                <div className="flex items-center gap-1">
                    <span className="icon loader-icon icon-size-20" />
                    <p className="text bg text-white">{isRecording ? t('stopping') : t('starting')}</p>
                </div>
            ) : isRecording ? (
                <div className="flex flex-row items-center gap-1">
                    <div className="flex items-center gap-1">
                        <span className="icon stop-icon icon-size-20" />
                        <p className="text bg text-white">{t('stopRecordingButton')}</p>
                    </div>
                    <p className="record-button-duration text bg text-white items-center">{formatDuration(recordingDuration)}</p>
                </div>
            ) : (
                <div className="flex items-center gap-1">
                    <span className="icon record-icon icon-size-20" />
                    <p className="text bg text-white">{t('startRecordingButton')}</p>
                </div>
            )}
        </button>
    );

    if (isDisabled && tooltipText) {
        return (
            <div className="tooltip-wrapper pos-rel flex flex-1 w-full" style={{opacity: 0.5, cursor: "not-allowed"}}>
                {buttonEl}
                <div className={clsx("tooltip-container elevated-sharp pos-bottom p-01 br-2 bg-dark")}>
                    <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid">
                        <p className="text-white text md">{tooltipText}</p>
                    </div>
                </div>
            </div>
        );
    }

    return buttonEl;
};
