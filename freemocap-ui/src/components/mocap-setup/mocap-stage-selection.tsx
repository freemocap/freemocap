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

const NOTHING_TO_RUN = '';

const START_INFO = {
    title: 'Start processing from',
    text: <>
        <p>Processing is a chain of stages. The chosen stage and every stage after it run again; every stage before it reuses its saved result.</p>
        <p>A stage can only be chosen when the stage before it has a saved result.</p>
        <p><em>Reusing 2D tracking keeps the detector settings it was produced with. Reusing triangulation keeps its calibration and coordinate frame, so start from triangulation to change calibration or alignment.</em></p>
        <p>Completed results replace the selected saved run.</p>
    </>,
};

const SAVED_RESULT_INFO = {
    title: 'Saved result',
    text: <p>The saved run and sensor group whose stages are reused. Reprocessing replaces this run.</p>,
};

const choiceKey = (choice: {run_id: number; sensor_group: string}): string =>
    JSON.stringify([choice.run_id, choice.sensor_group]);

/** The first stage after the last saved one, or null when every stage is saved. */
const defaultStart = (choice: SavedChoice | undefined): number | null => {
    const lastSaved = PROCESSING_STAGES.reduce(
        (last, [stage], index) => choice?.stages[stage] ? index : last, -1);
    return lastSaved + 1 < PROCESSING_STAGES.length ? lastSaved + 1 : null;
};

export default function MocapStageSelection({path, onChange}: {
    path: string | null; onChange: (selection: StageSelection | null) => void;
}) {
    const [inventory, setInventory] = useState<Inventory | null>(null);
    const [error, setError] = useState('');
    const [selected, setSelected] = useState('');
    const [start, setStart] = useState<number | null>(null);

    const choices: SavedChoice[] = inventory?.runs.flatMap(
        run => run.groups.map(group => ({...group, run_id: run.run_id}))) ?? [];
    const choice = choices.find(item => choiceKey(item) === selected);

    useEffect(() => {
        const controller = new AbortController();
        setInventory(null);
        setError('');
        setStart(null);
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
        if (inventory) setStart(defaultStart(choice));
        // `choice` is derived from `inventory` and `selected`.
    }, [inventory, selected]);

    useEffect(() => {
        onChange(inventory && start !== null ? {
            startStage: PROCESSING_STAGES[start][0],
            baseRunId: choice?.run_id ?? 0,
            sensorGroup: choice?.sensor_group,
        } : null);
    }, [inventory, start, selected, onChange]);

    if (!path) return <p className="settings-note">Select a recording folder to inspect saved stages.</p>;
    if (error) return <p role="alert" className="settings-note settings-note-error">Could not inspect saved stages: {error}</p>;
    if (!inventory) return <p role="status" className="settings-note">Checking saved processing stages…</p>;

    const isSaved = (index: number): boolean => Boolean(choice?.stages[PROCESSING_STAGES[index][0]]);
    const startOptions: {value: string; label: string}[] = PROCESSING_STAGES
        .map(([, label], index) => ({value: String(index), label, available: index === 0 || isSaved(index - 1)}))
        .filter(option => option.available)
        .map(({value, label}) => ({value, label}));
    if (start === null) startOptions.unshift({value: NOTHING_TO_RUN, label: 'All stages saved — choose one to rerun'});

    return <>
        {choices.length > 1 && <SettingRow label="Saved result" info={SAVED_RESULT_INFO}
            control={<SettingSelectInput label="Saved result" value={selected}
                options={choices.map(item => ({value: choiceKey(item), label: `Run ${item.run_id} · ${item.sensor_group}`}))}
                onChange={setSelected}/>}/>}

        <SettingRow promoted label="Start processing from" info={START_INFO}
            control={<SettingSelectInput label="Start processing from"
                value={start === null ? NOTHING_TO_RUN : String(start)} options={startOptions}
                onChange={value => setStart(value === NOTHING_TO_RUN ? null : Number(value))}/>}/>

        <ol className="mocap-stage-list">
            {PROCESSING_STAGES.map(([stage, label], index) => {
                const runs = start !== null && index >= start;
                const status = runs ? (isSaved(index) ? 'Rerun' : 'Run')
                    : isSaved(index) ? (start === null ? 'Saved' : 'Reuse saved') : 'Not saved';
                return <li key={stage} className={`mocap-stage${runs ? ' mocap-stage-runs' : ''}`}>
                    <span className="mocap-stage-index">{index + 1}</span>
                    <span className="mocap-stage-label">{label}</span>
                    <SettingsSummaryChip tone={runs ? 'positive' : 'quiet'}>{status}</SettingsSummaryChip>
                </li>;
            })}
        </ol>
    </>;
}
