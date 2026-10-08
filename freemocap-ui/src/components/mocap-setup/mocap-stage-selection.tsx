import {useEffect, useState} from 'react';
import {serverUrls} from '@/constants/server-urls';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

import {PROCESSING_STAGES, type ResumeStage, type StageSelection} from '@/services/recording/posthoc-processing';
interface SavedGroup {sensor_group: string; stages: Record<ResumeStage, boolean>}
interface Inventory {selected_run_id: number; runs: {run_id: number; groups: SavedGroup[]}[]}

export default function MocapStageSelection({path, onChange}: {
    path: string | null; onChange: (selection: StageSelection | null) => void;
}) {
    const [inventory, setInventory] = useState<Inventory | null>(null);
    const [error, setError] = useState('');
    const [selected, setSelected] = useState('');
    const [start, setStart] = useState<number | null>(null);
    const stages = PROCESSING_STAGES;
    const choices = inventory?.runs.flatMap(run => run.groups.map(group => ({...group, run_id: run.run_id}))) ?? [];
    const group = choices.find(item => JSON.stringify([item.run_id, item.sensor_group]) === selected);

    useEffect(() => {
        const controller = new AbortController();
        setInventory(null);
        setError('');
        setStart(null);
        onChange(null);
        if (!path) return () => controller.abort();
        void (async () => {
            try {
                const response = await fetch(`${serverUrls.endpoints.processMocapRecording}/stages?recording_path=${encodeURIComponent(path)}`,
                    {signal: controller.signal});
                if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
                const data: Inventory = await response.json();
                if (controller.signal.aborted) return;
                setInventory(data);
                const run = data.runs.find(item => item.run_id === data.selected_run_id) ?? data.runs[0];
                setSelected(run?.groups[0] ? JSON.stringify([run.run_id, run.groups[0].sensor_group]) : '');
            } catch (reason) {
                if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
            }
        })();
        return () => controller.abort();
    }, [path, onChange]);

    useEffect(() => {
        if (!inventory) return;
        const lastSaved = stages.reduce((last, [stage], index) => group?.stages[stage] ? index : last, -1);
        setStart(lastSaved + 1 < stages.length ? lastSaved + 1 : null);
    }, [inventory, selected]);

    useEffect(() => {
        onChange(inventory && start !== null ? {
            startStage: PROCESSING_STAGES[start][0], baseRunId: group?.run_id ?? 0,
            sensorGroup: group?.sensor_group,
        } : null);
    }, [inventory, start, selected, onChange]);

    if (!path) return <p>Select a recording folder to inspect saved stages.</p>;
    if (error) return <p role="alert">Could not inspect saved stages: {error}</p>;
    if (!inventory) return <p role="status">Checking saved processing stages…</p>;
    return <div className="flex flex-col gap-2">
        {choices.length > 1 && <label>Saved result <select aria-label="Saved result" value={selected}
            onChange={event => setSelected(event.target.value)}>
            {choices.map(item => <option key={JSON.stringify([item.run_id, item.sensor_group])}
                value={JSON.stringify([item.run_id, item.sensor_group])}>
                Run {item.run_id} · {item.sensor_group}
            </option>)}
        </select></label>}
        <p>Check the first stage to rerun. Dependent stages rerun with it; earlier stages use saved results.</p>
        {stages.map(([stage, label], index) => {
            const checked = start !== null && index >= start;
            const required = checked && (index > start! || !group?.stages[stage]);
            const missingInput = index > 0 && !group?.stages[PROCESSING_STAGES[index - 1][0]];
            return <label key={stage} className="flex flex-row align-center gap-2">
                <input type="checkbox" checked={checked} disabled={required || missingInput}
                    onChange={() => setStart(checked ? (index + 1 < stages.length ? index + 1 : null) : index)}/>
                <span>{label} — {checked ? (group?.stages[stage] ? 'Rerun' : 'Run') :
                    (group?.stages[stage] ? 'Use saved result' : 'Not needed for this run')}</span>
            </label>;
        })}
        {start === null && <p>Saved results are available. Select a stage to reprocess.</p>}
        <p>Reusing 2D tracking keeps its detector settings. Reusing triangulation keeps its coordinate frame;
            select triangulation to change calibration or alignment. Completed results replace the selected run.</p>
    </div>;
}
