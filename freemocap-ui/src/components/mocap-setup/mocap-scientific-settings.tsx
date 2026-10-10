import {useEffect, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {scientificExportFormatsUpdated, scientificExportDataUpdated, scientificExportAfterProcessingUpdated} from '@/store/slices/mocap';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {type ExportChannel, type ScientificExportData, type ScientificExportFormat} from '@/types/scientific-exports';
import MocapCsvSettings from './mocap-csv-settings';
import {electronIpc} from '@/services/electron-ipc/electron-ipc';
import './scientific-export-settings.css';

interface Selection {
    revision: string; selected_run_id: number;
    runs: {run_id: number; channels: {selection: ExportChannel; names: number; components: string[]}[]}[];
}
interface Job {
    job_id: string; status: 'queued' | 'running' | 'complete' | 'failed' | 'cancelled';
    detail: string; completed_channels: number; total_channels: number;
    result?: {files: string[]; manifest_path: string};
}

export default function MocapScientificSettings({path, processing}: {path: string | null; processing: boolean}) {
    const dispatch = useAppDispatch();
    const config = useAppSelector(state => state.mocap.config);
    const formats = config.scientificExportFormats ?? [];
    const data = config.scientificExportData ?? ['LANDMARKS_3D'];
    const [selection, setSelection] = useState<Selection | null>(null);
    const [run, setRun] = useState(0);
    const [keep, setKeep] = useState(false);
    const [job, setJob] = useState<Job | null>(null);
    const [starting, setStarting] = useState(false);
    const [error, setError] = useState('');
    const [noSavedResult, setNoSavedResult] = useState(false);
    const [refresh, setRefresh] = useState(0);
    const base = `${serverUrls.getHttpUrl()}/freemocap/exports`;
    const busy = starting || job?.status === 'queued' || job?.status === 'running';
    const available = selection?.runs.find(r => r.run_id === run)?.channels ?? [];
    const choices: {key: ScientificExportData; label: string}[] = [
        {key:'LANDMARKS_3D', label:'3D landmarks'},
        {key:'KEYPOINTS_3D', label:'3D keypoints - filtered'},
        {key:'RAW_KEYPOINTS_3D', label:'3D keypoints - raw triangulated'},
        {key:'OVERLAY_2D', label:'2D keypoints - one file per camera'},
        {key:'SEGMENT_POSES', label:'Rigid-body segments - positions and world quaternions'},
    ];
    const unavailable = data.some(kind => !available.some(a => a.selection.channel === kind));
    const validSelection = data.length > 0 && !unavailable;
    const selected = available.filter(a => data.includes(a.selection.channel as ScientificExportData));
    const minimumFiles = (formats.includes('notebook') ? 1 : 0) + (formats.includes('npz') ? 1 : 0) + (formats.includes('npy') ? selected.length + 2 : 0)
        + (formats.includes('wide_csv') ? selected.reduce((n, c) => n + Math.ceil(c.names*c.components.length/1024), 0) : 0);

    useEffect(() => {
        const controller = new AbortController();
        setNoSavedResult(false);
        setSelection(null); setError('');
        if (!path || processing) return () => controller.abort();
        void (async () => {
            try {
                const response = await fetch(`${base}/scientific?recording_path=${encodeURIComponent(path)}`, {signal: controller.signal});
                if (response.status === 204) {
                    if (!controller.signal.aborted) setNoSavedResult(true);
                    return;
                }
                if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
                const data: Selection = await response.json();
                if (!controller.signal.aborted) {setSelection(data); setRun(data.selected_run_id);}
            } catch (reason) {
                if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
            }
        })();
        return () => controller.abort();
    }, [path, processing, refresh, base]);

    useEffect(() => {
        if (!job || !['queued', 'running'].includes(job.status)) return;
        const controller = new AbortController();
        const timer = window.setTimeout(() => void (async () => {
            try {
                const response = await fetch(`${base}/jobs/${job.job_id}`, {signal: controller.signal});
                if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
                const next: Job = await response.json();
                if (!controller.signal.aborted) setJob(next);
            } catch (reason) {
                if (!controller.signal.aborted) {
                    setError(reason instanceof Error ? reason.message : String(reason));
                    setJob(previous => previous ? {...previous, status: 'failed', detail: 'Could not retrieve export status; the job may still be running.'} : null);
                }
            }
        })(), 500);
        return () => {controller.abort(); window.clearTimeout(timer);};
    }, [job, base]);

    async function save() {
        if (!selection || !path || busy || !validSelection || !formats.length) return;
        setStarting(true); setError(''); setJob(null);
        try {
            const response = await fetch(`${base}/scientific`, {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({recording_path: path, run_id: run, expected_revision: selection.revision,
                    formats, data, keep})});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            const result: {job_id: string} = await response.json();
            setJob({...result, status: 'queued', detail: 'Queued', completed_channels: 0, total_channels: 0});
        } catch (reason) {setError(reason instanceof Error ? reason.message : String(reason));}
        finally {setStarting(false);}
    }

    async function cancel() {
        if (!job) return;
        try {
            const response = await fetch(`${base}/jobs/${job.job_id}/cancel`, {method: 'POST'});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            setJob(await response.json());
        } catch (reason) {setError(reason instanceof Error ? reason.message : String(reason));}
    }

    return <div className="scientific-export-settings">
        <p className="settings-note">Choose the data to export, then its file formats. Export saved results without repeating processing.</p>
        <fieldset disabled={busy || processing}>
            <legend>Formats</legend>
            {(['wide_csv', 'npy', 'npz', 'notebook'] as ScientificExportFormat[]).map(format => <label key={format}>
                <input type="checkbox" checked={formats.includes(format)} onChange={e => dispatch(scientificExportFormatsUpdated(
                    e.target.checked ? [...formats, format] : formats.filter(f => f !== format)))}/>
                {{wide_csv:'Wide CSV', npy:'NumPy NPY', npz:'NumPy NPZ package', notebook:'Jupyter Notebook Explorer'}[format]}</label>)}
            <label><input type="checkbox" checked={config.scientificExportAfterProcessing ?? false}
                onChange={e => dispatch(scientificExportAfterProcessingUpdated(e.target.checked))}/> Export selected formats after processing</label>
            <label>Saved run <select aria-label="Scientific export run" value={run} disabled={!selection}
                onChange={e => setRun(Number(e.target.value))}>
                {selection ? selection.runs.map(r => <option key={r.run_id} value={r.run_id}>Run {r.run_id}</option>) : <option value={run}>No saved result</option>}
            </select></label>
            <div role="group" aria-label="Data to export">
                {choices.map(({key, label}) => <label key={key}><input type="checkbox" checked={data.includes(key)}
                    onChange={e => dispatch(scientificExportDataUpdated(e.target.checked ? [...data, key] : data.filter(d => d !== key)))}/>
                    {label}</label>)}
            </div>
            {unavailable && selection && <p role="alert">Some selected data is unavailable in this run. Update the selection.</p>}
            {data.length === 0 && <p role="alert">Select at least one data type.</p>}
            {formats.includes('notebook') && <p className="settings-note">Notebook Explorer reads the selected Parquet data with Pandas and Matplotlib in Jupyter or VS Code. Keep it with the recording; save your edited analysis under a new filename.</p>}
            {selection && validSelection && formats.length > 0 && <p>At least {minimumFiles} data files and one compact export metadata file.
                {formats.includes('npy') && ' NPY files go in npy/: each measurement file contains values; one shared .frames file contains frame numbers and one shared .timestamps file contains seconds; unavailable values are NaN. CSV files go in csv/.'}</p>}
            <label><input type="checkbox" checked={keep} onChange={e => setKeep(e.target.checked)}/> Keep this export in a run folder (do not replace it)</label>
            <button type="button" onClick={() => void save()} disabled={!selection || !validSelection || !formats.length}>Export saved result</button>
            <button type="button" onClick={() => setRefresh(r => r + 1)} disabled={!path}>Reload saved results</button>
        </fieldset>
        {busy && <button type="button" onClick={() => void cancel()} disabled={!job}>Cancel export</button>}
        {job && <p role={job.status === 'failed' ? 'alert' : 'status'}>{job.detail}{job.total_channels > 0 ? ` (${job.completed_channels}/${job.total_channels} channels)` : ''}</p>}
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
        <details><summary>Tall CSV diagnostic export</summary><MocapCsvSettings path={path} processing={processing || !!busy}/></details>
    </div>;
}
