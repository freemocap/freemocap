import {useEffect, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store';
import {serverUrls} from '@/constants/server-urls';
import {calibrateRecording, loadCalibrationToml} from '@/store/slices/calibration';
import {calibrationTomlPathCleared, selectMocapRecordingPath} from '@/store/slices/mocap/mocap-slice';

interface CalibrationFileOptions {recording_path: string | null; most_recent_path: string | null}

export function RecordingCalibrationOptions(): React.ReactElement {
    const dispatch = useAppDispatch();
    const directory = useAppSelector(selectMocapRecordingPath);
    const calibrationRunning = useAppSelector(state => state.calibration.isLoading || state.calibration.isRecording);
    const [options, setOptions] = useState<CalibrationFileOptions | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        const controller = new AbortController();
        let abortLoad: (() => void) | null = null;
        setOptions(null); setError(null);
        dispatch(calibrationTomlPathCleared());
        if (!directory) return;
        void (async () => {
            try {
                const query = new URLSearchParams({recording_directory: directory});
                const response = await fetch(`${serverUrls.getHttpUrl()}/freemocap/calibration/files?${query}`, {signal: controller.signal});
                if (!response.ok) throw new Error(await response.text());
                const result: CalibrationFileOptions = await response.json();
                if (controller.signal.aborted) return;
                setOptions(result);
                if (result.recording_path) {
                    const loading = dispatch(loadCalibrationToml({path: result.recording_path, force: true}));
                    abortLoad = loading.abort;
                    await loading.unwrap();
                }
            } catch (failure) {
                if (!controller.signal.aborted) setError(String(failure));
            }
        })();
        return () => {controller.abort(); abortLoad?.();};
    }, [directory, dispatch]);

    const useMostRecent = async (): Promise<void> => {
        if (!options?.most_recent_path) return;
        setBusy(true); setError(null);
        try {
            await dispatch(loadCalibrationToml({path: options.most_recent_path, force: true})).unwrap();
            dispatch(calibrationTomlPathCleared());
        } catch (failure) {setError(String(failure));}
        finally {setBusy(false);}
    };
    const calibrateFolder = async (): Promise<void> => {
        setBusy(true); setError(null);
        try {await dispatch(calibrateRecording()).unwrap();}
        catch (failure) {setError(String(failure));}
        finally {setBusy(false);}
    };
    return <div className="flex flex-col gap-1 p-1">
        <span className="text sm" title={options?.recording_path ?? undefined}>
            {options?.recording_path ? 'Calibration found in this recording' : 'No calibration selected from this folder'}
        </span>
        <button disabled={busy || !options?.most_recent_path} onClick={() => void useMostRecent()}>Use most recent calibration</button>
        <button disabled={busy || calibrationRunning || !directory} onClick={() => void calibrateFolder()}>Calibrate videos in selected folder</button>
        <span className="text sm">Runs the calibration task separately. Videos must contain the configured calibration board.</span>
        {error && <p role="alert" className="text-error">{error}</p>}
    </div>;
}
