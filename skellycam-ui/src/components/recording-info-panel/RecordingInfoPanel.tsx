import React, {useEffect, useState} from "react";
import {useAppDispatch, useAppSelector} from "@/store";
import {
    StartStopRecordingButton
} from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import {
    MicrophoneSelector
} from "@/components/recording-info-panel/recording-subcomponents/MicrophoneSelector";
import {startRecording, stopRecording, recordingInfoUpdated} from "@/store";
import {useElectronIPC} from "@/services/electron-ipc/electron-ipc";
import {useServer} from "@/services/server/ServerContextProvider";
import {getTimestampString} from "@/components/recording-info-panel/getTimestampString";
import {RecordingCompleteDialog} from "@/components/recording-info-panel/RecordingCompleteDialog";
import {RecordingPathModal} from "@/components/recording-info-panel/RecordingPathModal";
import ButtonSm from "@/components/ui-components/ButtonSm";
import TextSelector from "@/components/ui-components/TextSelector";
import { useTranslation } from "react-i18next";

interface RecordingOperation {
    type: 'start' | 'stop';
    timestamp: number;
}

export const RecordingInfoPanel: React.FC = () => {
    const dispatch = useAppDispatch();
    const recordingInfo = useAppSelector((state) => state.recording);
    const { t } = useTranslation();

    const [createSubfolder, setCreateSubfolder] = useState<boolean>(false);
    const [useDelayStart, setUseDelayStart] = useState<boolean>(false);
    const [delaySeconds, setDelaySeconds] = useState<number>(3);
    const [countdown, setCountdown] = useState<number | null>(null);
    const [pendingOperation, setPendingOperation] = useState<RecordingOperation | null>(null);
    const [recordingStartTime, setRecordingStartTime] = useState<number | null>(null);
    const [useTimestamp, setUseTimestamp] = useState<boolean>(true);
    const [useIncrement, setUseIncrement] = useState<boolean>(false);
    const [currentIncrement, setCurrentIncrement] = useState<number>(1);
    const [baseName, setBaseName] = useState<string>("recording");
    const [customSubfolderName, setCustomSubfolderName] = useState<string>("");
    const [recordingTag, setRecordingTag] = useState<string>("");
    const [micDeviceIndex, setMicDeviceIndex] = useState<number>(-1);
    const [pathModalOpen, setPathModalOpen] = useState<boolean>(false);

    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();
    const noCamerasConnected = connectedCameraIds.length === 0;

    useEffect(() => {
        if (pendingOperation) {
            const isNowRecording = recordingInfo.isRecording;
            const wasStarting = pendingOperation.type === 'start';
            const wasStopping = pendingOperation.type === 'stop';
            if ((wasStarting && isNowRecording) || (wasStopping && !isNowRecording)) {
                setPendingOperation(null);
                if (wasStarting && isNowRecording) setRecordingStartTime(Date.now());
                else if (wasStopping && !isNowRecording) setRecordingStartTime(null);
            }
            if (Date.now() - pendingOperation.timestamp > 5000) {
                console.error(`Recording ${pendingOperation.type} timed out`);
                setPendingOperation(null);
            }
        }
    }, [recordingInfo.isRecording, pendingOperation]);

    useEffect(() => {
        if (recordingInfo.isRecording && !recordingStartTime) setRecordingStartTime(Date.now());
    }, []);

    useEffect(() => {
        if (recordingInfo?.recordingDirectory?.startsWith("~") && isElectron && api) {
            api.fileSystem.getHomeDirectory.query()
                .then((homePath: string) => {
                    const updated = recordingInfo.recordingDirectory.replace("~", homePath).replace(/\\/g, "/");
                    dispatch(recordingInfoUpdated({recordingDirectory: updated}));
                })
                .catch((error: unknown) => { console.error("Failed to get home directory:", error); throw error; });
        }
    }, [recordingInfo.recordingDirectory, isElectron, api, dispatch]);

    useEffect(() => {
        if (countdown !== null && countdown > 0) {
            const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
            return () => clearTimeout(timer);
        } else if (countdown === 0) {
            handleStartRecording();
            setCountdown(null);
        }
    }, [countdown]);

    const buildRecordingName = (): string => {
        const parts: string[] = [];
        if (useTimestamp) parts.push(getTimestampString());
        else parts.push(baseName);
        if (recordingTag) parts.push(recordingTag);
        return parts.join("_");
    };

    const handleStartRecording = async (): Promise<void> => {
        const recordingName = buildRecordingName();
        const subfolderName = createSubfolder ? (customSubfolderName || getTimestampString()) : "";
        const recordingPath = createSubfolder
            ? `${recordingInfo.recordingDirectory}/${subfolderName}`
            : recordingInfo.recordingDirectory;
        if (useIncrement) setCurrentIncrement((prev) => prev + 1);
        setPendingOperation({ type: 'start', timestamp: Date.now() });
        try {
            await dispatch(startRecording({ recordingName, recordingDirectory: recordingPath, micDeviceIndex })).unwrap();
        } catch (error) {
            console.error("Failed to start recording:", error);
            setPendingOperation(null);
            throw error;
        }
    };

    const handleRecordButtonClick = async (): Promise<void> => {
        if (pendingOperation) return;
        if (recordingInfo.isRecording) {
            setPendingOperation({ type: 'stop', timestamp: Date.now() });
            try {
                await dispatch(stopRecording()).unwrap();
            } catch (error) {
                console.error("Failed to stop recording:", error);
                setPendingOperation(null);
                throw error;
            }
        } else if (useDelayStart) {
            setCountdown(delaySeconds);
        } else {
            await handleStartRecording();
        }
    };

    const recordingName = buildRecordingName() + (useIncrement ? `_${currentIncrement}` : '');
    const subfolderName = createSubfolder ? (customSubfolderName || undefined) : undefined;
    const displayPath = (createSubfolder && customSubfolderName)
        ? `${recordingInfo.recordingDirectory}/${customSubfolderName}/${recordingName}`
        : `${recordingInfo.recordingDirectory}/${recordingName}`;

    return (
    <div className="main-side-actions flex flex-col gap-1 z-3">
        <div className="file-directory-group bg-middark br-2 p-1 flex flex-col gap-1 br-1 p-1 pb-2">
            <p className="text-nowrap text-left bg-md text-darkgray p-1">File directory</p>
                <div className="button-sm-group gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black full-width" style={{pointerEvents: "none"}}>
                    <span className="icon icon-size-20 subfolder-icon" />
                    <p className="text-gray text-nowrap text md text-align-left flex flex-end">
                        {displayPath || "Set recording path"}
                    </p>
                </div>
                <div className="flex flex-row gap-1 items-center">
                    <TextSelector
                        value={recordingTag}
                        onChange={setRecordingTag}
                        placeholder={t("recordingTagPlaceholder")}
                    />
                    <ButtonSm
                        iconClass="settings-icon"
                        text="Recording Options"
                        textColor="text-gray"
                        onClick={() => setPathModalOpen(true)}
                    />
                </div>

                <RecordingCompleteDialog />

                <RecordingPathModal
                    open={pathModalOpen}
                    onClose={() => setPathModalOpen(false)}
                    recordingDirectory={recordingInfo.recordingDirectory}
                    recordingName={recordingName}
                    subfolder={subfolderName}
                    countdown={countdown}
                    recordingTag={recordingTag}
                    useDelayStart={useDelayStart}
                    delaySeconds={delaySeconds}
                    useTimestamp={useTimestamp}
                    baseName={baseName}
                    useIncrement={useIncrement}
                    currentIncrement={currentIncrement}
                    createSubfolder={createSubfolder}
                    customSubfolderName={customSubfolderName}
                    isRecording={recordingInfo.isRecording}
                    onDelayToggle={setUseDelayStart}
                    onDelayChange={setDelaySeconds}
                    onTagChange={setRecordingTag}
                    onNameChange={(value) => { setUseTimestamp(false); setBaseName(value); }}
                    onUseTimestampChange={setUseTimestamp}
                    onBaseNameChange={setBaseName}
                    onUseIncrementChange={setUseIncrement}
                    onIncrementChange={setCurrentIncrement}
                    onCreateSubfolderChange={setCreateSubfolder}
                    onCustomSubfolderNameChange={setCustomSubfolderName}
                />
            </div>
            {/* Title */}
            {/* <div className="flex items-center gap-1 h-25">
                <span className="icon stream-icon icon-size-20" />
                <p className="text bg text-white">Record</p>
            </div> */}
        <div className="record-group bg-middark br-2 p-1 flex flex-col gap-1 br-1 p-2 pb-2">
            {/* Record button — full width, its own row */}
            <div className="flex flex-row flex-1 items-center gap-1 fit-content w-full min-w-full" onClick={(e) => e.stopPropagation()} onMouseDown={(e) => e.stopPropagation()}>
                <StartStopRecordingButton
                    isRecording={recordingInfo.isRecording}
                    isPending={pendingOperation !== null}
                    countdown={countdown}
                    recordingStartTime={recordingStartTime}
                    disabled={noCamerasConnected && !recordingInfo.isRecording}
                    tooltipText={noCamerasConnected && !recordingInfo.isRecording ? t('connectCamerasToRecord') : undefined}
                    onClick={handleRecordButtonClick}
                />
            </div>
                    
            {/* Microphone */}
            <MicrophoneSelector
                selectedMicIndex={micDeviceIndex}
                onMicSelected={setMicDeviceIndex}
                disabled={recordingInfo.isRecording}
            />
        </div>
        
     </div>
    );
};
