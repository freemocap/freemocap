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
import {RecordingPathPanel} from '@/components/control-panels/recording-info-panel/RecordingPathPanel';
import {RecordingControlPanel} from '@/components/control-panels/recording-info-panel/RecordingControlPanel';
import {MocapPanel} from '@/components/control-panels/mocap-control-panel/MocapPanel';

const MONO_FONT = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';

const ORIGIN_LABEL_KEY: Record<string, string> = {
    'pending-capture': 'activeRecording.origin.pendingCapture',
    'just-captured': 'activeRecording.origin.justCaptured',
    'browsed': 'activeRecording.origin.browsed',
    'auto-latest': 'activeRecording.origin.autoLatest',
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
        <div className="flex flex-col w-full overflow-y overflow-hidden bg-dark h-full" style={{border: '1px solid var(--color-border-secondary)'}}>
            <div className="flex flex-col p-2 gap-2">
                <ErrorBoundary>
                    {!recordingName ? (
                        <div className="pl-4 pr-4" style={{paddingTop: 32}}>
                            <div className="flex flex-col gap-2">
                                <p className="text sm text-gray" style={{fontStyle: 'italic'}}>
                                    {t('activeRecording.none')}
                                </p>
                                <div className="flex flex-row gap-1 mt-1">
                                    <button className="button sm secondary" onClick={() => navigate('/streaming')}>
                                        {t('activeRecording.goToStreaming')}
                                    </button>
                                    <button className="button sm secondary" onClick={() => navigate('/browse')}>
                                        {t('activeRecording.browseRecordings')}
                                    </button>
                                </div>
                            </div>
                            <RecordingPathPanel />
                            <RecordingControlPanel />
                        </div>
                    ) : (
                        <>
                            <div className="p-2 br-1 border-1 border-mid-black">
                                <div className="flex flex-row items-center gap-1 mb-1 flex-wrap">
                                    <p className="text bg text-white m-0" style={{fontFamily: MONO_FONT, fontWeight: 600}}>
                                        {recordingName}
                                    </p>
                                    {origin && (
                                        <span className="tag text sm">
                                            {ORIGIN_LABEL_KEY[origin] ? t(ORIGIN_LABEL_KEY[origin]) : origin}
                                        </span>
                                    )}
                                </div>
                                <p
                                    title={fullPath ?? ''}
                                    className="text sm text-gray m-0 overflow-hidden"
                                    style={{fontFamily: MONO_FONT, textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}
                                >
                                    {fullPath}
                                </p>
                                <div className="flex flex-row gap-1 mt-2 flex-wrap">
                                    <button className="button sm secondary" onClick={handleOpenFolder}>
                                        <span className="icon load-icon icon-size-20"/>
                                        {t('openFolder')}
                                    </button>
                                    <button className="button sm secondary" onClick={() => navigate('/playback')}>
                                        <span className="icon play-icon icon-size-20"/>
                                        {t('activeRecording.openInPlayback')}
                                    </button>
                                    <button className="button sm secondary" onClick={handleOpenInBlender}>
                                        <span className="icon expand-icon icon-size-20"/>
                                        {t('activeRecording.openInBlender')}
                                    </button>
                                    <button className="button sm secondary" onClick={() => navigate('/browse')}>
                                        <span className="icon load-icon icon-size-20"/>
                                        {t('activeRecording.browseRecordings')}
                                    </button>
                                </div>
                            </div>

                            <div className="p-2 br-1 border-1 border-mid-black">
                                <p className="text md text-white m-0" style={{fontWeight: 600}}>{t('activeRecording.pipelineStages')}</p>
                                <RecordingStatusPanel
                                    status={status}
                                    isLoading={statusLoading}
                                    error={statusError}
                                    onRefresh={refreshStatus}
                                    defaultExpanded
                                    recordingFolderPath={fullPath}
                                />
                            </div>

                            <MocapPanel/>
                        </>
                    )}
                </ErrorBoundary>
            </div>
            <footer className="p-1">
                <Footer/>
            </footer>
        </div>
    );
};

const PathRow: React.FC<{ label: string; value: string }> = ({label, value}) => (
    <div className="flex flex-row gap-1 items-center">
        <span className="text sm text-gray" style={{minWidth: 160}}>{label}</span>
        <span
            className="text sm overflow-hidden"
            style={{fontFamily: MONO_FONT, textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}
        >
            {value}
        </span>
    </div>
);

export default ActiveRecordingPage;
