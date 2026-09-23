import {useMemo, useState} from 'react';
import {Matrix4} from 'three';
import {useAppDispatch, useAppSelector} from '@/store';
import {
    bodyAlignmentEnabledUpdated,
    referenceTransformEnabledUpdated,
    referenceTransformUpdated,
    selectReferenceTransform,
    selectReferenceTransformEnabled,
} from '@/store/slices/mocap';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';
import TransformEditor from './transform-editor';
import ReferenceTransformSummary from './reference-transform-summary';
import PosthocCalibrationSave from './posthoc-calibration-save';
import {transformFields, transformFromFields, TransformRepresentation} from './reference-transform';

const TRANSFORM_INFO = {
    title: "Custom transformation",
    text: <>
        <p>Define an <strong>additional transformation</strong> applied last, after person alignment when enabled.</p>
        <p><strong>Accept transformation</strong> keeps your definition in this panel. Switching this option off retains it for later editing.</p>
        <p>Applied to calibrated multicamera processing, including all reconstructed points and cameras. Translation is in millimeters, using X right, Y forward, Z up. Live preview is unchanged.</p>
    </>,
};

export default function ReferenceFrameSettings() {
    const [editorOpen, setEditorOpen] = useState(false);
    const dispatch = useAppDispatch();

    /* The definition lives in the store, so it survives closing this modal.
       reference-transform.ts already owns the row-major <-> Matrix4 mapping;
       both directions go through it rather than through a second copy of
       that layout. */
    const storedTransform = useAppSelector(selectReferenceTransform);
    const transformEnabled = useAppSelector(selectReferenceTransformEnabled);
    const personAlignmentEnabled = useAppSelector(state => state.mocap.config.bodyAlignmentEnabled);
    const transformation = useMemo(
        () => storedTransform ? transformFromFields(storedTransform, TransformRepresentation.Matrix) : null,
        [storedTransform],
    );
    const setTransformEnabled = (enabled: boolean) => dispatch(referenceTransformEnabledUpdated(enabled));
    const setTransformation = (matrix: Matrix4 | null) => dispatch(referenceTransformUpdated(
        matrix ? transformFields(matrix, TransformRepresentation.Matrix) : null));
    return <>
        <SettingsGroupHeading text="Mocap capture volume alignment" info={{
            title: 'Processing alignment',
            text: <p>These options transform reconstructed points and cameras during
                posthoc Mocap processing. The calibration file changes only when you
                explicitly save the processed transforms.</p>,
        }}/>
        <SettingRow label="Align to person" info={{
            title: 'Align to person',
            text: <>
                <p>Use the tracked person to establish the capture volume's position
                    and orientation, regardless of the loaded calibration's previous
                    alignment. Any enabled custom transform is applied afterward.</p>
                <p><strong>Keeping multiple trials consistent:</strong> Align one
                    representative trial and save its alignment to the calibration
                    file. Use that calibration with Align to person turned off for
                    subsequent trials. Keep the cameras fixed and use the same custom
                    transform settings so floor markings and stationary objects retain
                    consistent 3D coordinates.</p>
            </>,
        }} control={<SettingToggleSwitch label="Align to person"
            isToggled={personAlignmentEnabled}
            onToggle={enabled => dispatch(bodyAlignmentEnabledUpdated(enabled))}/>}/>
        <SettingRow label="Apply custom transform" info={TRANSFORM_INFO}
            control={<SettingToggleSwitch label="Apply custom transform" isToggled={transformEnabled}
                onToggle={setTransformEnabled}/>}/>
        {personAlignmentEnabled && transformEnabled && transformation &&
            <SettingsSummaryChip>
                The custom transform is applied after person alignment.
            </SettingsSummaryChip>}

        {/* The definition and its editor are shown unconditionally. The switch
            above decides whether the transform is applied, never whether the
            feature can be found. */}
        <div className={`reference-transform-block${transformEnabled ? '' : ' reference-transform-block-inactive'}`}>
            {transformation && <ReferenceTransformSummary matrix={transformation}/>}
            <div className="reference-transform-actions">
                {transformation && <ButtonSm text="Reset" className="secondary reference-frame-edit"
                    onClick={() => setTransformation(null)}/>}
                <ButtonSm text="Reference frame…"
                    className="secondary reference-frame-edit" textColor="text-white" onClick={() => setEditorOpen(true)}/>
            </div>
        </div>

        {editorOpen && <TransformEditor initialMatrix={transformation ?? new Matrix4()}
            onAccept={matrix => {setTransformation(matrix); setTransformEnabled(true); setEditorOpen(false);}}
            onClose={() => setEditorOpen(false)}/>}
        <PosthocCalibrationSave/>
    </>;
}

