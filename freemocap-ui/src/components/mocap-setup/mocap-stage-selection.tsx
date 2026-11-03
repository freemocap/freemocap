import {useAppDispatch, useAppSelector} from '@/store/hooks';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';
import {
    choiceKey, choiceSelected, saveModeSelected, stageToggled,
    selectStageChoice, selectStageChoices, selectStageRows, type RunSaveMode,
} from '@/store/slices/processing-stages';

const SAVED_RESULT_INFO = {
    title: 'Starting data',
    text: <p>Choose the saved run and camera group supplying inputs. Save results below determines whether this run is overwritten or preserved.</p>,
};

/** The Processing stages controls; the owner loads the saved-stage inventory with useSavedStageInventory. */
export default function MocapStageSelection({path}: {path: string | null}) {
    const dispatch = useAppDispatch();
    const inventory = useAppSelector(state => state.processingStages.inventory);
    const error = useAppSelector(state => state.processingStages.inventoryError);
    const selected = useAppSelector(state => state.processingStages.choiceKey);
    const saveMode = useAppSelector(state => state.processingStages.saveMode);
    const choices = useAppSelector(selectStageChoices);
    const choice = useAppSelector(selectStageChoice);
    const rows = useAppSelector(selectStageRows);

    if (!path) return <p className="settings-note">Select a recording folder to inspect saved stages.</p>;
    if (error) return <p role="alert" className="settings-note settings-note-error">Could not inspect saved stages: {error}</p>;
    if (!inventory) return <p role="status" className="settings-note">Checking saved processing stages…</p>;

    return <>
        <SettingRow label="Starting data" info={SAVED_RESULT_INFO}
            control={<SettingSelectInput label="Starting data" value={selected} disabled={!choices.length}
                options={choices.length ? choices.map(item => ({value: choiceKey(item), label: `Run ${item.run_id}${item.run_id === 0 ? ' — Default' : ''} · ${item.sensor_group}`}))
                    : [{value: '', label: 'New recording — Run 0'}]}
                onChange={value => dispatch(choiceSelected(value))}/>}/>
        <SettingRow label="Save results" info={{title: 'Save results', text: <p>Overwrite updates the selected run after successful computation. Keep creates a new run and preserves the source run.</p>}}
            control={<SettingSelectInput label="Save results" value={saveMode} disabled={!choices.length}
                options={[{value: 'overwrite', label: 'Overwrite selected run'},
                    {value: 'new_run', label: 'Keep selected run; create a new run'}]}
                onChange={value => dispatch(saveModeSelected(value as RunSaveMode))}/>}/>
        <p className="settings-note" role="status">
            {saveMode === 'new_run' && choices.length
                ? `Read from Run ${choice?.run_id ?? 0} → save as a new run. Preserve the original run; generated files use run-ID names and folders.`
                : `Update Run ${choice?.run_id ?? 0}. Successful saves replace requested data and remove dependent downstream Parquet results. Generated files overwrite matching names.`}
            {' '}Existing exported files remain until their replacements are generated. Changing these controls does not change saved data.
        </p>

        <p className="settings-note">Check a stage to run it and all later stages. Uncheck a later stage to finish before it.
            Uncheck the first selected stage to reuse its saved result, if available.</p>

        <ol className="mocap-stage-list">
            {rows.map((row, index) => <li key={row.stage} className={`mocap-stage${row.runs ? ' mocap-stage-runs' : ''}`}>
                <input id={`mocap-stage-${row.stage}`} type="checkbox" checked={row.runs} disabled={!row.canSelect}
                    onChange={event => dispatch(stageToggled({index, checked: event.target.checked}))}/>
                <label htmlFor={`mocap-stage-${row.stage}`} className="mocap-stage-label">{row.label}</label>
                <SettingsSummaryChip tone={row.runs ? 'active' : row.outcome === 'Removed after save' ? 'caution' : 'quiet'}>{row.outcome}</SettingsSummaryChip>
            </li>)}
        </ol>
        <p className="settings-note">Reused tracking keeps its original detector settings. Reused 3D points keep their coordinate frame.
            Start at triangulation to change calibration or alignment. Save results controls whether completed work updates the selected run or creates a separate run.</p>
        <p className="settings-note">Saving 3D results includes the requested coordinate alignment.
            Alignment and its trajectory preparation run before saving, even when finishing at triangulation.
            Finishing early also excludes final file and Blender exports.</p>
    </>;
}
