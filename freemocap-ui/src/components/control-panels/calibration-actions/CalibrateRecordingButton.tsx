import {useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store';
import {PipelineType, selectGroupedPipelinesAll} from '@/store/slices/pipelines';
import {calibrateRecording} from '@/store/slices/calibration';

export function CalibrateRecordingButton({recordingPath}: {recordingPath: string | null | undefined}): React.ReactElement {
    const dispatch = useAppDispatch();
    const running = useAppSelector(state => state.calibration.isLoading || state.calibration.isRecording);
    const processing = useAppSelector(state => selectGroupedPipelinesAll(state).some(
        group => group.pipelineType === PipelineType.CALIBRATION && group.isActive,
    ));
    const busy = running || processing;
    const [error, setError] = useState<string | null>(null);
    const startCalibration = async (): Promise<void> => {
        if (!recordingPath) throw new Error('Select a recording to calibrate');
        setError(null);
        try {await dispatch(calibrateRecording({recordingPath})).unwrap();}
        catch (failure) {setError(String(failure));}
    };
    return <div className="flex flex-col gap-1">
        <button className="button sm secondary w-full" disabled={!recordingPath || busy}
            title={recordingPath ?? 'Select a recording in Playback'} onClick={() => void startCalibration()}>
            {busy ? 'Calibration in progress' : 'Calibrate active recording'}
        </button>
        <span className="text sm">Uses the configured calibration board and existing recording videos.</span>
        {error && <p role="alert" className="text-error text sm">{error}</p>}
    </div>;
}
