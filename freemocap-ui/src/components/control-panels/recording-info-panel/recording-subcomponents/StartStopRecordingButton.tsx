import React, {useEffect, useState} from 'react';
import clsx from 'clsx';
import {useTranslation} from 'react-i18next';

interface StartStopButtonProps {
    isRecording: boolean;
    isPending: boolean;
    countdown: number | null;
    recordingStartTime: number | null;
    onClick: () => void;
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
    isRecording, isPending, countdown, recordingStartTime, onClick,
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

    // The button never gates itself. `isRecording` is live server truth
    // (app_state.recording_in_progress) and only decides whether a click sends start
    // or stop; `isPending` only drives the in-flight label. The button always sends —
    // the server reconciles the request and reports back.
    const buttonEl = (
        <button
            data-onboarding="recording:start-recording"
            className={clsx(
                "accent text-nowrap flex flex-row flex-1 gap-1 br-1 button sm min-w-fit-content flex-inline text-left items-center full-width primary justify-center",
                isRecording ? "record-button-active" : isPending ? "record-button-pending" : "accent",
            )}
            onClick={onClick}
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

    return buttonEl;
};
