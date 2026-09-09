import ButtonSm from "@/components/ui-components/ButtonSm";
import {CalibrateRecordingButton} from '@/components/control-panels/calibration-actions/CalibrateRecordingButton';
import {useEffect, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store';
import {serverUrls} from '@/constants/server-urls';
import {loadCalibrationToml} from '@/store/slices/calibration';
import {selectMocapRecordingPath} from '@/store/slices/mocap/mocap-slice';

interface CalibrationFileOptions {recording_path: string | null; most_recent_path: string | null}

export function RecordingCalibrationOptions(): React.ReactElement {
    const dispatch = useAppDispatch();
    const directory = useAppSelector(selectMocapRecordingPath);
    const [options, setOptions] = useState<CalibrationFileOptions | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        const controller = new AbortController();
        setOptions(null); setError(null);
        if (!directory) return;
        void (async () => {
            try {
                const query = new URLSearchParams({recording_directory: directory});
                const response = await fetch(`${serverUrls.getHttpUrl()}/freemocap/calibration/files?${query}`, {signal: controller.signal});
                if (!response.ok) throw new Error(await response.text());
                const result: CalibrationFileOptions = await response.json();
                if (controller.signal.aborted) return;
                setOptions(result);
            } catch (failure) {
                if (!controller.signal.aborted) setError(String(failure));
            }
        })();
        return () => {controller.abort();};
    }, [directory, dispatch]);

    const loadSelection = async (path: string | null): Promise<void> => {
        if (!path) throw new Error('Calibration file is unavailable.');
        setBusy(true); setError(null);
        try {
            await dispatch(loadCalibrationToml({path, force: true})).unwrap();
        } catch (failure) {setError(String(failure));}
        finally {setBusy(false);}
    };
    return <div className="flex flex-col gap-1 p-1">
        <span className="text sm" title={options?.recording_path ?? undefined}>
            {options?.recording_path ? 'Calibration found in this recording' : 'No calibration file in this folder'}
        </span>
        <ButtonSm iconClass="tomlfile-icon" text="Use this recording's calibration" className="full-width"
            disabled={busy || !options?.recording_path} onClick={() => void loadSelection(options?.recording_path ?? null)}/>
        <ButtonSm iconClass="tomlfile-icon" text="Use most recent calibration" className="full-width"
            disabled={busy || !options?.most_recent_path} onClick={() => void loadSelection(options?.most_recent_path ?? null)}/>
        <CalibrateRecordingButton recordingPath={directory}/>
        <span className="text sm">Runs the calibration task separately. Videos must contain the configured calibration board.</span>
        {error && <p role="alert" className="text-error">{error}</p>}
    </div>;
}
