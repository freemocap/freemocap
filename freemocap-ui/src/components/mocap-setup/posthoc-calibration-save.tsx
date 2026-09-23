import {useAppDispatch, useAppSelector} from '@/store';
import {selectPlaybackBundle} from '@/store/slices/playback-data/playback-data-slice';
import {saveCalibrationTransform} from '@/store/slices/calibration/calibration-save';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import './posthoc-calibration-save.css';
import ReferenceTransformSummary from './reference-transform-summary';
import {transformFromFields, TransformRepresentation} from './reference-transform';

export default function PosthocCalibrationSave() {
    const dispatch = useAppDispatch();
    const active = useAppSelector(state => state.activeRecording);
    const bundle = useAppSelector(selectPlaybackBundle(active.recordingName, active.baseDirectory));
    const calibration = useAppSelector(state => state.calibration);
    const processing = useAppSelector(state => state.mocap.isLoading);
    const realtimeBusy = useAppSelector(state => state.realtime.isLoading);
    const manifest = bundle?.manifest;
    const run = manifest?.runs.find(item => item.run_id === manifest.selected_run_id);
    const updates = Object.entries(run?.calibration_updates ?? {});
    if (!updates.length) return null;

    const busy = processing || realtimeBusy || calibration.isSaving
        || calibration.isLoading || calibration.isRecording || Boolean(calibration.loadRequestId);
    return <div className="posthoc-calibration-save">
        <SettingsGroupHeading text="Save processed transforms" info={{title: 'Save processed transforms', text: <>
            <p>Saves the transformations from the selected completed run into its source calibration file, in the recorded order.</p>
            <p>The source calibration must still match the revision used for processing. Saving clears a matching manual offset; newer edits are retained.</p>
        </>}}/>
        {updates.map(([group, request]) => {
            const selected = calibration.loadedCalibration;
            const matches = selected?.path === request.path
                && selected.mtimeMs === request.expected_mtime_ms;
            return <div key={group} className="posthoc-calibration-save-entry">
                <span className="posthoc-calibration-save-source" title={request.path}>
                    {group} · {request.path.split(/[\\/]/).pop()}
                </span>
                {request.transformations.map((entry, index) => <div key={index}>
                    <span className="posthoc-calibration-save-operation">
                        {entry.operation} transform
                    </span>
                    <ReferenceTransformSummary
                    label={`Processed ${entry.operation} transform`}
                    matrix={transformFromFields(
                        [...entry.translation_mm, ...entry.quaternion_wxyz],
                        TransformRepresentation.Quaternion,
                    )}
                    />
                </div>)}
                <ButtonSm
                    className="posthoc-calibration-save-button"
                    text={calibration.isSaving ? 'Saving…' : 'Apply processed transforms to calibration file'}
                    buttonType="secondary"
                    title={request.path}
                    disabled={busy || !matches}
                    onClick={() => {void dispatch(saveCalibrationTransform(request));}}
                />
                {!matches && <p className="text sm text-gray">
                    Select the unchanged source calibration used by this run to save its transforms.
                </p>}
            </div>;
        })}
        {calibration.error && <p role="alert" className="text-error">{calibration.error}</p>}
    </div>;
}
