import React, {useCallback} from 'react';
import {useNavigate} from 'react-router-dom';
import {Footer} from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import {RecordingStatusPanel} from '@/components/common/RecordingStatusPanel';
import {useRecordingStatus} from '@/hooks/useRecordingStatus';
import {useAppSelector} from '@/store';
import {
    selectActiveRecordingBaseDirectory,
    selectActiveRecordingFullPath,
    selectActiveRecordingName,
    selectActiveRecordingOrigin,
    selectActiveRecordingStructure,
} from '@/store/slices/active-recording/active-recording-slice';
import {useElectronIPC} from '@/services';
import {useTranslation} from 'react-i18next';
import {useBlender} from "@/hooks/useBlender";
import {RecordingInfoPanel} from '@/components/control-panels/recording-info-panel/RecordingInfoPanel';
import {CalibrationPanel} from '@/components/control-panels/calibration-control-panel/CalibrationPanel';
import {MocapPanel} from '@/components/control-panels/mocap-control-panel/MocapPanel';

const MONO_FONT = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';

const ORIGIN_LABEL: Record<string, string> = {
    'pending-capture': 'Pending capture',
    'just-captured': 'Just captured',
    'browsed': 'Browsed',
    'auto-latest': 'Auto-loaded',
};

const ActiveRecordingPage: React.FC = () => {
    const {t} = useTranslation();
    const navigate = useNavigate();
    const {api} = useElectronIPC();

    const {triggerOpenInBlender} = useBlender();

    const recordingName = useAppSelector(selectActiveRecordingName);
    const baseDirectory = useAppSelector(selectActiveRecordingBaseDirectory);
    const fullPath = useAppSelector(selectActiveRecordingFullPath);
    const origin = useAppSelector(selectActiveRecordingOrigin);
    const structure = useAppSelector(selectActiveRecordingStructure);
    const {
        status,
        isLoading: statusLoading,
        error: statusError,
        refresh: refreshStatus,
    } = useRecordingStatus(recordingName, {
        autoFetch: !!recordingName,
        recordingParentDirectory: baseDirectory,
    });

    const handleOpenFolder = useCallback(async () => {
        if (!fullPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({path: fullPath});
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    }, [fullPath, api]);

    const handleOpenInBlender = useCallback(async () => {
        if (!fullPath) return;
        void triggerOpenInBlender(fullPath);
    }, [structure?.blendPath, triggerOpenInBlender]);

    return (
        <div className="flex flex-col w-full overflow-y overflow-hidden bg-dark" style={{height: '100%', border: '1px solid var(--color-border-secondary)'}}>
            <div className="flex flex-col p-2 gap-2">
                <ErrorBoundary>
                    {!recordingName ? (
                        <div style={{paddingTop: 32, paddingLeft: 16, paddingRight: 16}}>
                            <div className="flex flex-col gap-2">
                                <p className="text sm text-gray" style={{fontStyle: 'italic'}}>
                                    No active recording. This folder will be created when you start recording.
                                </p>
                                <div className="flex flex-row gap-1" style={{marginTop: 4}}>
                                    <button className="button sm secondary" onClick={() => navigate('/streaming')}>
                                        Go to Streaming
                                    </button>
                                    <button className="button sm secondary" onClick={() => navigate('/browse')}>
                                        Browse recordings
                                    </button>
                                </div>
                            </div>
                            <RecordingInfoPanel/>
                        </div>
                    ) : (
                        <>
                            <div className="p-2 br-1 border-1 border-mid-black">
                                <div className="flex flex-row items-center gap-1" style={{marginBottom: 4, flexWrap: 'wrap'}}>
                                    <p className="text bg text-white" style={{fontFamily: MONO_FONT, fontWeight: 600, margin: 0}}>
                                        {recordingName}
                                    </p>
                                    {origin && (
                                        <span className="tag text sm">
                                            {ORIGIN_LABEL[origin] ?? origin}
                                        </span>
                                    )}
                                </div>
                                <p
                                    title={fullPath ?? ''}
                                    className="text sm text-gray"
                                    style={{fontFamily: MONO_FONT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: 0}}
                                >
                                    {fullPath}
                                </p>
                                <div className="flex flex-row gap-1" style={{marginTop: 8, flexWrap: 'wrap'}}>
                                    <button className="button sm secondary" onClick={handleOpenFolder}>
                                        <span className="icon load-icon icon-size-20"/>
                                        {t('openFolder')}
                                    </button>
                                    <button className="button sm secondary" onClick={() => navigate('/playback')}>
                                        <span className="icon play-icon icon-size-20"/>
                                        Open in Playback
                                    </button>
                                    <button className="button sm secondary" onClick={handleOpenInBlender}>
                                        <span className="icon expand-icon icon-size-20"/>
                                        Open in Blender
                                    </button>
                                    <button className="button sm secondary" onClick={() => navigate('/browse')}>
                                        <span className="icon load-icon icon-size-20"/>
                                        Browse recordings
                                    </button>
                                </div>
                            </div>

                            <div className="p-2 br-1 border-1 border-mid-black">
                                <p className="text md text-white" style={{fontWeight: 600, marginBottom: 4, margin: 0}}>Pipeline stages</p>
                                <RecordingStatusPanel
                                    status={status}
                                    isLoading={statusLoading}
                                    error={statusError}
                                    onRefresh={refreshStatus}
                                    defaultExpanded
                                    recordingFolderPath={fullPath}
                                />
                            </div>

                            <CalibrationPanel/>
                            <MocapPanel/>
                        </>
                    )}
                </ErrorBoundary>
            </div>
            <footer style={{padding: 4}}>
                <Footer/>
            </footer>
        </div>
    );
};

const PathRow: React.FC<{ label: string; value: string }> = ({label, value}) => (
    <div className="flex flex-row gap-1 items-center">
        <span className="text sm text-gray" style={{minWidth: 160}}>{label}</span>
        <span
            className="text sm"
            style={{fontFamily: MONO_FONT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}
        >
            {value}
        </span>
    </div>
);

export default ActiveRecordingPage;
