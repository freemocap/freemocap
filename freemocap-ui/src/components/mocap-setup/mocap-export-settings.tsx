import {serverClient, recordingRequest} from '@/services/server/sdk';
import {useEffect, useState, type ReactNode} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {exportSettingsReset, exportFormatsUpdated, exportChannelsUpdated, exportAfterProcessingUpdated} from '@/store/slices/mocap';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {type ExportChannel, type ExportChannelKind, type ExportFormat} from '@/types/recording-exports';
import MocapCsvSettings from './mocap-csv-settings';
import {electronIpc} from '@/services/electron-ipc/electron-ipc';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import {createRecordingExport, recordingExportUrl} from '@/services/recording/recording-exports';

const DATA_INFO = {
    title: 'Data',
    text: <p>Choose which saved measurements to export. Every selected format receives the same data.</p>,
};
const FORMATS_INFO = {
    title: 'Formats',
    text: <p>Choose the file formats to write into the recording’s exports folder.</p>,
};
const DATA_ROW_INFO: Record<ExportChannelKind, {title: string; text: ReactNode}> = {
    LANDMARKS_3D: {title: '3D landmarks', text: <p>Model landmarks placed by each solved segment pose and the fitted scale.</p>},
    KEYPOINTS_3D: {title: '3D keypoints - filtered', text: <p>Tracker-named 3D keypoints after gap filling and filtering.</p>},
    RAW_KEYPOINTS_3D: {title: '3D keypoints - raw triangulated', text: <p>Tracker-named 3D keypoints as triangulated, before gap filling and filtering.</p>},
    OVERLAY_2D: {title: '2D keypoints - camera observations', text: <p>Each camera’s 2D tracker observations.</p>},
    SEGMENT_POSES: {title: 'Rigid-body segments', text: <p>Each segment’s origin position and world orientation quaternion.</p>},
};
const FORMAT_INFO: Record<ExportFormat, {title: string; text: ReactNode}> = {
    wide_csv: {title: 'Wide CSV', text: <p>One table per selected channel. Wide CSV files go in csv/.</p>},
    npz: {title: 'NumPy NPZ archive', text: <p>Packages the dataset in one archive. Load it with SkellyForge.</p>},
    npy: {title: 'NumPy NPY arrays (optional)', text: <p>A secondary output: multiple array files and dataset.json in npy/, for direct NumPy access or memory mapping. Load it with SkellyForge.</p>},
    notebook: {title: 'Jupyter Notebook Explorer', text: <p>Reads the selected Parquet data with Polars and plots it with Plotly in Jupyter or VS Code. Keep it with the recording; save your edited analysis under a new filename.</p>},
};
const AFTER_INFO = {
    title: 'Export selected formats after processing',
    text: <p>Write the selected formats when a processing attempt finishes. Automatic exports use the processing attempt’s destination run.</p>,
};
const RUN_GROUP_INFO = {
    title: 'Run now',
    text: <p>Export results that are already saved, without repeating processing.</p>,
};
const EXPORT_NOW_INFO = {
    title: 'Export a saved run',
    text: <p>Export the run selected under Processing stages with the data and formats chosen above.</p>,
};
const RELOAD_INFO = {
    title: 'Saved results',
    text: <p>Read the recording’s saved runs again, for example after processing finished in another window.</p>,
};
const FORMAT_LABELS: Record<ExportFormat, string> = {
    wide_csv: 'Wide CSV', npz: 'NumPy NPZ archive', npy: 'NumPy NPY arrays (optional)', notebook: 'Jupyter Notebook Explorer',
};

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
                const response = await serverClient().responses.get_export_options_freemocap_recordings__recording_id__export_options_get({...recordingRequest(path!),signal: controller.signal});
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
                const response = await serverClient().responses.get_task_freemocap_tasks__task_id__get({path:{task_id:job.task_id},signal: controller.signal});
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
            const response = await serverClient().responses.cancel_task_freemocap_tasks__task_id__cancel_post({path:{task_id:job.task_id},});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            setJob(await response.json());
        } catch (reason) {setError(reason instanceof Error ? reason.message : String(reason));}
    }

    const locked = busy || processing;
    return <div className="export-settings">
        {migrationError && <div role="alert" className="settings-note settings-note-error settings-note-dismissable">
            <span>{migrationError}</span>
            <ButtonSm text="Reset export settings" className="setting-action-button" textColor="text-white"
                onClick={() => dispatch(exportSettingsReset())}/>
        </div>}
        <p className="settings-note">Choose the data to export, then its file formats. Export saved results without repeating processing.</p>

        <SettingsGroupHeading text="Data" info={DATA_INFO}/>
        <div role="group" aria-label="Data to export">
            {choices.map(({key, label}) => <SettingRow key={key} label={label} info={DATA_ROW_INFO[key]}
                control={<SettingToggleSwitch label={label} isToggled={data.includes(key)} disabled={locked}
                    onToggle={on => dispatch(exportChannelsUpdated(on ? [...data, key] : data.filter(d => d !== key)))}/>}/>)}
        </div>
        {unavailable && selection && <p role="alert" className="settings-note settings-note-error">Some selected data is unavailable in this run. Update the selection.</p>}
        {data.length === 0 && <p role="alert" className="settings-note settings-note-error">Select at least one data type.</p>}

        <SettingsGroupHeading text="Formats" info={FORMATS_INFO}/>
        {(['wide_csv', 'npz', 'npy', 'notebook'] as ExportFormat[]).map(format => <SettingRow key={format}
            label={FORMAT_LABELS[format]} info={FORMAT_INFO[format]}
            control={<SettingToggleSwitch label={FORMAT_LABELS[format]} isToggled={formats.includes(format)} disabled={locked}
                onToggle={on => dispatch(exportFormatsUpdated(on ? [...formats, format] : formats.filter(f => f !== format)))}/>}/>)}
        <p className="settings-note">NPZ packages the dataset in one archive. NPY is an optional secondary output:
            multiple array files and dataset.json in npy/, for direct NumPy access or memory mapping.
            Load either format with SkellyForge.</p>
        {formats.some(format => format === 'npy' || format === 'npz') && <p className="settings-note">
            Each channel keeps its values, timestamps, names, units, and available quality information.
            Fitted scales and lengths are stored without a time axis.</p>}
        <SettingRow label="Export selected formats after processing" info={AFTER_INFO}
            control={<SettingToggleSwitch label="Export selected formats after processing" disabled={locked}
                isToggled={config.exportAfterProcessing ?? false}
                onToggle={on => dispatch(exportAfterProcessingUpdated(on))}/>}/>

        <SettingsGroupHeading text="Run now" info={RUN_GROUP_INFO}/>
        <SettingRow label={`Export saved Run ${run}`} info={EXPORT_NOW_INFO}
            control={<ButtonSm text="Export saved result" className="setting-action-button" textColor="text-white"
                disabled={locked || !selection || !validSelection || !formats.length} onClick={() => void save()}/>}/>
        <SettingRow label="Saved results" info={RELOAD_INFO}
            control={<ButtonSm text="Reload saved results" className="setting-action-button" textColor="text-white"
                disabled={!path || locked} onClick={() => setRefresh(r => r + 1)}/>}/>
        {busy && <SettingRow label="Export in progress" info={{title: 'Export in progress', text: <p>Stop this export. Files already validated stay in place.</p>}}
            control={<ButtonSm text="Cancel export" className="setting-action-button" textColor="text-white"
                disabled={!job} onClick={() => void cancel()}/>}/>}
        {job && <p role={job.status === 'failed' ? 'alert' : 'status'} className={job.status === 'failed' ? 'settings-note settings-note-error' : 'settings-note'}>
            {job.progress.detail}{job.progress.progress_fraction !== null ? ` (${Math.round(job.progress.progress_fraction * 100)}%)` : ''}</p>}
        {noSavedResult && <p role="status" className="settings-note">No saved result yet. Process the recording to export saved data.</p>}
        {error && <p role="alert" className="settings-note settings-note-error">{error}</p>}
        {job?.status === 'complete' && job.result && <div className="settings-note">
            <p>Saved and validated {job.result.files.length} {job.result.files.length === 1 ? 'file' : 'files'}. Metadata: {job.result.manifest_path}</p>
            {electronIpc && <ButtonSm text="Open output folder" className="setting-action-button" textColor="text-white" onClick={() => {
                if (!electronIpc) return;
                const folder = job.result!.manifest_path.replace(/[\\/][^\\/]+$/, '');
                void electronIpc.fileSystem.openFolder.mutate({path: folder}).then(opened => {
                    if (!opened) setError('Could not open the export folder.');
                }).catch(reason => setError(String(reason)));
            }}/>}
        </div>}
        <details className="settings-disclosure"><summary>Tall CSV diagnostic export</summary>
            <MocapCsvSettings sourceRunId={sourceRunId} path={path} processing={processing || !!busy}/>
        </details>
    </div>;
}
