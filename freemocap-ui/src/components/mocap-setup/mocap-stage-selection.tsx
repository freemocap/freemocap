import {useEffect, useState} from 'react';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';
import {PROCESSING_STAGES, type ResumeStage, type StageSelection} from '@/services/recording/posthoc-processing';

interface SavedGroup {sensor_group: string; stages: Record<ResumeStage, boolean>}
interface Inventory {selected_run_id: number; runs: {run_id: number; groups: SavedGroup[]}[]}
interface SavedChoice extends SavedGroup {run_id: number}

const SAVED_RESULT_INFO = {
    title: 'Starting data',
    text: <p>Choose the saved run and camera group supplying inputs. Save results below determines whether this run is overwritten or preserved.</p>,
};

const choiceKey = (choice: {run_id: number; sensor_group: string}): string =>
    JSON.stringify([choice.run_id, choice.sensor_group]);

/** Resume at the first missing stage; later saved results cannot fill an earlier gap. */
const defaultStart = (choice: SavedChoice | undefined): number | null => {
    const missing = PROCESSING_STAGES.findIndex(([stage]) => !choice?.stages[stage]);
    return missing < 0 ? null : missing;
};

export default function MocapStageSelection({path, onChange, onSourceRunChange}: {
    path: string | null; onSourceRunChange?: (run: number) => void; onChange: (selection: StageSelection | null) => void;
}) {
    const [inventory, setInventory] = useState<Inventory | null>(null);
    const [saveMode, setSaveMode] = useState<'overwrite' | 'new_run'>('overwrite');
    const [error, setError] = useState('');
    const [selected, setSelected] = useState('');
    const [start, setStart] = useState<number | null>(null);
    const [stop, setStop] = useState(PROCESSING_STAGES.length - 1);

    const choices: SavedChoice[] = inventory?.runs.flatMap(
        run => run.groups.map(group => ({...group, run_id: run.run_id}))) ?? [];
    const choice = choices.find(item => choiceKey(item) === selected);

    useEffect(() => {
        const controller = new AbortController();
        setInventory(null);
        setError('');
        setStart(null);
        setSaveMode('overwrite');
        if (!path) return () => controller.abort();
        void (async () => {
            try {
                const response = await fetch(
                    `${serverUrls.endpoints.processMocapRecording}/stages?recording_path=${encodeURIComponent(path)}`,
                    {signal: controller.signal});
                if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
                const data: Inventory = await response.json();
                if (controller.signal.aborted) return;
                const run = data.runs.find(item => item.run_id === data.selected_run_id) ?? data.runs[0];
                setInventory(data);
                setSelected(run?.groups[0] ? choiceKey({run_id: run.run_id, sensor_group: run.groups[0].sensor_group}) : '');
            } catch (reason) {
                if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
            }
        })();
        return () => controller.abort();
    }, [path]);

    // A different saved result has different saved stages, so the start resets to its default.
    useEffect(() => {
        if (inventory) {
            setStart(defaultStart(choice));
            setStop(PROCESSING_STAGES.length - 1);
        }
        // `choice` is derived from `inventory` and `selected`.
    }, [inventory, selected]);

    useEffect(() => {onSourceRunChange?.(choice?.run_id ?? 0);}, [selected, inventory, onSourceRunChange]);

    useEffect(() => {
        onChange(inventory && start !== null ? {
            startStage: PROCESSING_STAGES[start][0],
            stopStage: PROCESSING_STAGES[stop][0],
            baseRunId: choice?.run_id ?? 0,
            runSaveMode: saveMode,
            sensorGroup: choice?.sensor_group,
        } : null);
    }, [inventory, start, stop, selected, saveMode, onChange]);

    if (!path) return <p className="settings-note">Select a recording folder to inspect saved stages.</p>;
    if (error) return <p role="alert" className="settings-note settings-note-error">Could not inspect saved stages: {error}</p>;
    if (!inventory) return <p role="status" className="settings-note">Checking saved processing stages…</p>;

    const isSaved = (index: number): boolean => Boolean(choice?.stages[PROCESSING_STAGES[index][0]]);
    const toggleStage = (index: number, checked: boolean) => {
        if (checked) {
            setStart(start === null ? index : Math.min(start, index));
            setStop(PROCESSING_STAGES.length - 1);
        } else if (index === start) {
            // Removing the first selected stage can reuse its saved result.
            setStart(isSaved(index) && index < stop ? index + 1 : null);
        } else {
            setStop(index - 1);
        }
    };

    return <>
        <SettingRow label="Starting data" info={SAVED_RESULT_INFO}
            control={<SettingSelectInput label="Starting data" value={selected} disabled={!choices.length}
                options={choices.length ? choices.map(item => ({value: choiceKey(item), label: `Run ${item.run_id}${item.run_id === 0 ? ' — Default' : ''} · ${item.sensor_group}`}))
                    : [{value: '', label: 'New recording — Run 0'}]}
                onChange={setSelected}/>}/>
        <SettingRow label="Save results" info={{title: 'Save results', text: <p>Overwrite updates the selected run after successful computation. Keep creates a new run and preserves the source run.</p>}}
            control={<SettingSelectInput label="Save results" value={saveMode} disabled={!choices.length}
                options={[{value: 'overwrite', label: 'Overwrite selected run'},
                    {value: 'new_run', label: 'Keep selected run; create a new run'}]}
                onChange={value => setSaveMode(value as 'overwrite' | 'new_run')}/>}/>
        <p className="settings-note" role="status">
            {saveMode === 'new_run' && choices.length
                ? `Read from Run ${choice?.run_id ?? 0} → save as a new run. Preserve the original run; generated files use run-ID names and folders.`
                : `Update Run ${choice?.run_id ?? 0}. Successful saves replace requested data and remove dependent downstream Parquet results. Generated files overwrite matching names.`}
            {' '}Existing exported files remain until their replacements are generated. Changing these controls does not change saved data.
        </p>

        <p className="settings-note">Check a stage to run it and all later stages. Uncheck a later stage to finish before it.
            Uncheck the first selected stage to reuse its saved result, if available.</p>

        <ol className="mocap-stage-list">
            {PROCESSING_STAGES.map(([stage, label], index) => {
                const runs = start !== null && index >= start && index <= stop;
                const canSelect = runs || index === 0 || isSaved(index - 1)
                    || (start !== null && index > start);
                const status = runs ? (isSaved(index) ? 'Rerun' : 'Run')
                    : start !== null && index > stop ? (isSaved(index) ? (saveMode === 'new_run' ? 'In original run only' : 'Removed after save') : 'Not requested')
                    : isSaved(index) ? (start === null ? 'Saved' : 'Reuse saved') : 'Not saved';
                return <li key={stage} className={`mocap-stage${runs ? ' mocap-stage-runs' : ''}`}>
                    <input id={`mocap-stage-${stage}`} type="checkbox" checked={runs} disabled={!canSelect}
                        onChange={event => toggleStage(index, event.target.checked)}/>
                    <label htmlFor={`mocap-stage-${stage}`} className="mocap-stage-label">{label}</label>
                    <SettingsSummaryChip tone={runs ? 'positive' : 'quiet'}>{status}</SettingsSummaryChip>
                </li>;
            })}
        </ol>
        <p className="settings-note">Reused tracking keeps its original detector settings. Reused 3D points keep their coordinate frame.
            Start at triangulation to change calibration or alignment. Save results controls whether completed work updates the selected run or creates a separate run.</p>
        <p className="settings-note">Saving 3D results includes the requested coordinate alignment.
            Alignment and its trajectory preparation run before saving, even when finishing at triangulation.
            Finishing early also excludes final file and Blender exports.</p>
    </>;
}
