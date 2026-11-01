import {useEffect, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {exportSettingsReset, exportFormatsUpdated, exportChannelsUpdated, exportAfterProcessingUpdated} from '@/store/slices/mocap';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {type ExportChannel, type ExportChannelKind, type ExportFormat} from '@/types/recording-exports';
import MocapCsvSettings from './mocap-csv-settings';
import {electronIpc} from '@/services/electron-ipc/electron-ipc';
import './export-settings.css';
import {createRecordingExport, recordingExportUrl} from '@/services/recording/recording-exports';

interface Selection {
    revision: string; selected_run_id: number;
    runs: {run_id: number; channels: {selection: ExportChannel; names: number; components: string[]}[]}[];
}
interface Job {
    task_id: string; status: 'queued' | 'running' | 'complete' | 'failed' | 'cancelled';
    progress: {detail: string; progress_fraction: number | null};
    result?: {files: string[]; manifest_path: string};
}

export default function MocapExportSettings({path, processing, sourceRunId}: {path: string | null; processing: boolean; sourceRunId: number}) {
    const dispatch = useAppDispatch();
    const config = useAppSelector(state => state.mocap.config);
    const migrationError = useAppSelector(state => state.mocap.exportSettingsError);
    const formats = config.exportFormats ?? [];
    const data = config.exportChannels ?? ['LANDMARKS_3D'];
    const [selection, setSelection] = useState<Selection | null>(null);
    const run = sourceRunId;
    const [job, setJob] = useState<Job | null>(null);
    const [starting, setStarting] = useState(false);
    const [error, setError] = useState('');
    const [noSavedResult, setNoSavedResult] = useState(false);
    const [refresh, setRefresh] = useState(0);
    const optionsUrl = path ? recordingExportUrl(path, '/export-options') : null;
    const tasks = `${serverUrls.getHttpUrl()}/freemocap/tasks`;
    const busy = starting || job?.status === 'queued' || job?.status === 'running';
    const available = selection?.runs.find(r => r.run_id === run)?.channels ?? [];
    const choices: {key: ExportChannelKind; label: string}[] = [
        {key:'LANDMARKS_3D', label:'3D landmarks'},
        {key:'KEYPOINTS_3D', label:'3D keypoints - filtered'},
        {key:'RAW_KEYPOINTS_3D', label:'3D keypoints - raw triangulated'},
        {key:'OVERLAY_2D', label:'2D keypoints - camera observations'},
        {key:'SEGMENT_POSES', label:'Rigid-body segments - positions and world quaternions'},
    ];
    const unavailable = data.some(kind => !available.some(a => a.selection.channel === kind));
    const validSelection = data.length > 0 && !unavailable && !migrationError;

    useEffect(() => {
        const controller = new AbortController();
        setNoSavedResult(false);
        setSelection(null); setError('');
        if (!path || processing) return () => controller.abort();
        void (async () => {
            try {
                const response = await fetch(optionsUrl!, {signal: controller.signal});
                if (response.status === 204) {
                    if (!controller.signal.aborted) setNoSavedResult(true);
                    return;
                }
                if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
                const data: Selection = await response.json();
                if (!controller.signal.aborted) {setNoSavedResult(!data.revision); setSelection(data.revision ? data : null);}
            } catch (reason) {
                if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
            }
        })();
        return () => controller.abort();
    }, [path, processing, refresh, optionsUrl]);

    useEffect(() => {
        if (!job || !['queued', 'running'].includes(job.status)) return;
        const controller = new AbortController();
        const timer = window.setTimeout(() => void (async () => {
            try {
                const response = await fetch(`${tasks}/${encodeURIComponent(job.task_id)}`, {signal: controller.signal});
                if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
                const next: Job = await response.json();
                if (!controller.signal.aborted) setJob(next);
            } catch (reason) {
                if (!controller.signal.aborted) {
                    setError(reason instanceof Error ? reason.message : String(reason));
                    setJob(previous => previous ? {...previous, progress: {detail: 'Could not retrieve export status; retrying.', progress_fraction: null}} : null);
                }
            }
        })(), 500);
        return () => {controller.abort(); window.clearTimeout(timer);};
    }, [job, tasks]);

    async function save() {
        if (!selection || !path || busy || !validSelection || !formats.length) return;
        setStarting(true); setError(''); setJob(null);
        try {
            const result = await createRecordingExport(path, {kind: 'channels', run_id: run,
                expected_revision: selection.revision, formats, data, keep: false,
                ...(config.exportChannelOverrides ? {wide_csv: config.exportChannelOverrides} : {})});
            setJob({task_id: result.task_id, status: 'queued', progress: {detail: 'Queued', progress_fraction: null}});
        } catch (reason) {setError(reason instanceof Error ? reason.message : String(reason));}
        finally {setStarting(false);}
    }

    async function cancel() {
        if (!job) return;
        try {
            const response = await fetch(`${tasks}/${encodeURIComponent(job.task_id)}/cancel`, {method: 'POST'});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            setJob(await response.json());
        } catch (reason) {setError(reason instanceof Error ? reason.message : String(reason));}
    }

    return <div className="export-settings">
        {migrationError && <div role="alert">{migrationError}
            <button type="button" onClick={() => dispatch(exportSettingsReset())}>Reset export settings</button>
        </div>}
        <p className="settings-note">Choose the data to export, then its file formats. Export saved results without repeating processing.</p>
        <fieldset disabled={busy || processing}>
            <legend>Formats</legend>
            {(['wide_csv', 'npz', 'npy', 'notebook'] as ExportFormat[]).map(format => <label key={format}>
                <input type="checkbox" checked={formats.includes(format)} onChange={e => dispatch(exportFormatsUpdated(
                    e.target.checked ? [...formats, format] : formats.filter(f => f !== format)))}/>
                {{wide_csv:'Wide CSV', npy:'NumPy NPY arrays (optional)', npz:'NumPy NPZ archive', notebook:'Jupyter Notebook Explorer'}[format]}</label>)}
            <p className="settings-note">NPZ packages the dataset in one archive. NPY is an optional secondary output:
                multiple array files and dataset.json in npy/, for direct NumPy access or memory mapping.
                Load either format with SkellyForge.</p>
            <label><input type="checkbox" checked={config.exportAfterProcessing ?? false}
                onChange={e => dispatch(exportAfterProcessingUpdated(e.target.checked))}/> Export selected formats after processing</label>
            <p className="settings-note">Export saved Run {run}, selected under Processing stages.
                Automatic exports use the processing attempt’s destination run.</p>
            <div role="group" aria-label="Data to export">
                {choices.map(({key, label}) => <label key={key}><input type="checkbox" checked={data.includes(key)}
                    onChange={e => dispatch(exportChannelsUpdated(e.target.checked ? [...data, key] : data.filter(d => d !== key)))}/>
                    {label}</label>)}
            </div>
            {unavailable && selection && <p role="alert">Some selected data is unavailable in this run. Update the selection.</p>}
            {data.length === 0 && <p role="alert">Select at least one data type.</p>}
            {formats.includes('notebook') && <p className="settings-note">Notebook Explorer reads the selected Parquet data with Polars and plots it with Plotly in Jupyter or VS Code. Keep it with the recording; save your edited analysis under a new filename.</p>}
            {formats.some(format => format === 'npy' || format === 'npz') && <p className="settings-note">
                Each channel keeps its values, timestamps, names, units, and available quality information.
                Fitted scales and lengths are stored without a time axis.</p>}
            {formats.includes('wide_csv') && <p className="settings-note">Wide CSV files go in csv/.</p>}
            <button type="button" onClick={() => void save()} disabled={!selection || !validSelection || !formats.length}>Export saved result</button>
            <button type="button" onClick={() => setRefresh(r => r + 1)} disabled={!path}>Reload saved results</button>
        </fieldset>
        {busy && <button type="button" onClick={() => void cancel()} disabled={!job}>Cancel export</button>}
        {job && <p role={job.status === 'failed' ? 'alert' : 'status'}>{job.progress.detail}{job.progress.progress_fraction !== null ? ` (${Math.round(job.progress.progress_fraction * 100)}%)` : ''}</p>}
        {noSavedResult && <p role="status" className="settings-note">No saved result yet. Process the recording to export saved data.</p>}
        {error && <p role="alert">{error}</p>}
        {job?.status === 'complete' && job.result && <div className="settings-note">
            <p>Saved and validated {job.result.files.length} {job.result.files.length === 1 ? 'file' : 'files'}. Metadata: {job.result.manifest_path}</p>
            {electronIpc && <button type="button" onClick={() => {
                if (!electronIpc) return;
                const folder = job.result!.manifest_path.replace(/[\\/][^\\/]+$/, '');
                void electronIpc.fileSystem.openFolder.mutate({path: folder}).then(opened => {
                    if (!opened) setError('Could not open the export folder.');
                }).catch(reason => setError(String(reason)));
            }}>Open output folder</button>}
        </div>}
        <details><summary>Tall CSV diagnostic export</summary><MocapCsvSettings sourceRunId={sourceRunId} path={path} processing={processing || !!busy}/></details>
    </div>;
}
