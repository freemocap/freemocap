// Run-wide and per-stage controls of the Mocap processing window, shared by its outline, list and graph.
// Every control reads and writes the processing-stages store, which the processing request is built from.
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {
    choiceKey, choiceSelected, saveModeSelected, stageToggled,
    selectStageChoice, selectStageChoices, selectStageRows, type RunSaveMode,
} from '@/store/slices/processing-stages';
import {exportAfterProcessingUpdated} from '@/store/slices/mocap';
import {useBlender} from '@/hooks/useBlender';
import {PROCESSING_STAGES, type ResumeStage} from '@/services/recording/posthoc-processing';

/** The saved run and camera group that later stages read from. */
export function StartFromSelect() {
    const dispatch = useAppDispatch();
    const choices = useAppSelector(selectStageChoices);
    const selected = useAppSelector(state => state.processingStages.choiceKey);
    return <label className="mp-field">Start from
        <SettingSelectInput label="Starting data" value={selected} disabled={!choices.length}
            options={choices.length ? choices.map(item => ({value: choiceKey(item), label: `Run ${item.run_id}${item.run_id === 0 ? ' · default' : ''} · ${item.sensor_group}`}))
                : [{value: '', label: 'New recording · Run 0'}]}
            onChange={value => dispatch(choiceSelected(value))}/>
    </label>;
}

/** Whether completed work overwrites the selected run or is saved as a new one. */
export function SaveResultsSelect() {
    const dispatch = useAppDispatch();
    const choices = useAppSelector(selectStageChoices);
    const choice = useAppSelector(selectStageChoice);
    const saveMode = useAppSelector(state => state.processingStages.saveMode);
    return <label className="mp-field">Save results
        <SettingSelectInput label="Save results" value={saveMode} disabled={!choices.length}
            options={[{value: 'overwrite', label: `Overwrite Run ${choice?.run_id ?? 0}`}, {value: 'new_run', label: 'Save as a new run'}]}
            onChange={value => dispatch(saveModeSelected(value as RunSaveMode))}/>
    </label>;
}

/** Saved-stage inspection state: shown only while checking or when it failed. */
export function StageInventoryStatus() {
    const path = useAppSelector(state => state.processingStages.recordingPath);
    const inventory = useAppSelector(state => state.processingStages.inventory);
    const error = useAppSelector(state => state.processingStages.inventoryError);
    if (error) return <span role="alert" className="mp-inventory error">Could not inspect saved stages: {error}</span>;
    if (path && !inventory) return <span role="status" className="mp-inventory">Checking saved stages…</span>;
    return null;
}

export const stageRowIndex = (stage: ResumeStage): number => {
    const index = PROCESSING_STAGES.findIndex(([key]) => key === stage);
    if (index < 0) throw new Error(`Unknown processing stage "${stage}"`);
    return index;
};

/** Runs one processing stage, with the same dependency rules as every other stage control. */
export function StageToggle({stage, title}: {stage: ResumeStage; title: string}) {
    const dispatch = useAppDispatch();
    const rows = useAppSelector(selectStageRows);
    const index = stageRowIndex(stage);
    const row = rows[index];
    return <input type="checkbox" className="mp-stage-toggle" aria-label={title} checked={row.runs} disabled={!row.canSelect}
        onChange={event => dispatch(stageToggled({index, checked: event.target.checked}))}/>;
}

/** Where a stage's result comes from this run: computed now, or reused from a saved run. */
export function useStageOutcome(stage: ResumeStage): string {
    const rows = useAppSelector(selectStageRows);
    const choice = useAppSelector(selectStageChoice);
    const row = rows[stageRowIndex(stage)];
    if (row.runs) return row.outcome;
    return row.outcome === 'Reuse saved' ? `from Run ${choice?.run_id ?? 0}` : row.outcome;
}

export function BlenderToggle() {
    const {exportToBlenderEnabled, setExportToBlenderEnabled} = useBlender();
    return <SettingToggleSwitch label="Export to Blender after processing" isToggled={exportToBlenderEnabled} onToggle={setExportToBlenderEnabled}/>;
}

export function ExportsToggle() {
    const dispatch = useAppDispatch();
    const on = useAppSelector(state => state.mocap.config.exportAfterProcessing);
    return <SettingToggleSwitch label="Export files after processing" isToggled={on} onToggle={value => dispatch(exportAfterProcessingUpdated(value))}/>;
}

/** Shown when Blender export is on but no Blender was found; processing then skips the Blender step. */
export function BlenderMissingNotice() {
    const {effectiveBlenderExePath, exportToBlenderEnabled, isDetecting, redetectBlender} = useBlender();
    if (effectiveBlenderExePath || !exportToBlenderEnabled) return null;
    return <div role="alert" className="mp-blender-missing">
        <span>Blender not found. Get it at <a href="https://www.blender.org/download/" target="_blank" rel="noreferrer">blender.org/download</a>.</span>
        <button type="button" className="mp-small-button" disabled={isDetecting} onClick={redetectBlender}>{isDetecting ? 'Detecting…' : 'Detect again'}</button>
    </div>;
}
