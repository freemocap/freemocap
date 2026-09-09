import {useMemo, useState} from 'react';
import {Matrix4} from 'three';
import {useAppDispatch, useAppSelector} from '@/store';
import {
    bodyAlignmentUpdated,
    referenceTransformEnabledUpdated,
    referenceTransformUpdated,
    selectReferenceTransform,
    selectReferenceTransformEnabled,
} from '@/store/slices/mocap';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import TransformEditor from './transform-editor';
import {transformFields, transformFromFields, TransformRepresentation} from './reference-transform';

const REFERENCE_FRAME_INFO = {
    title: "Define reference frame",
    text: <>
        <p><strong>Calibration status</strong> is read from the selected calibration TOML.</p>
        <p>A saved <strong>ground plane</strong> takes precedence. Without one, <strong>Align to person</strong> is recommended.</p>
        <p>An additional transformation comes <em>after</em> alignment.</p>
    </>,
};

const GROUND_PLANE_INFO = {
    title: "Ground plane",
    text: <>
        <p>Read from the calibration TOML. When one is <strong>saved</strong>, it is used automatically and takes precedence over person alignment.</p>
        <p>With no saved ground plane, the capture volume keeps the calibration's own reference frame unless you align to the person.</p>
    </>,
};

const ALIGN_INFO = {
    title: "Align to person",
    text: <>
        <p><strong>Saved ground plane:</strong> used automatically when present in the calibration TOML. Person alignment is then unnecessary and disabled.</p>
        <p><strong>No saved ground plane:</strong> person alignment is on by default. It estimates upright direction from the body, including the head and face, and uses reliable foot contacts to estimate the floor.</p>
        <p><em>Turn it off to retain the calibration's reference frame.</em></p>
    </>,
};

const TRANSFORM_INFO = {
    title: "Custom transformation",
    text: <>
        <p>Define an <strong>additional transformation</strong> after alignment.</p>
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
    const transformation = useMemo(
        () => storedTransform ? transformFromFields(storedTransform, TransformRepresentation.Matrix) : null,
        [storedTransform],
    );
    const setTransformEnabled = (enabled: boolean) => dispatch(referenceTransformEnabledUpdated(enabled));
    const setTransformation = (matrix: Matrix4 | null) => dispatch(referenceTransformUpdated(
        matrix ? transformFields(matrix, TransformRepresentation.Matrix) : null));
    const fields = transformation ? transformFields(transformation, TransformRepresentation.Quaternion) : null;
    const preview = (values: number[]) => values.map(value => Number(value.toFixed(3))).join(', ');
    const enabled = useAppSelector(state => state.mocap.config.bodyAlignmentEnabled);
    const calibration = useAppSelector(state => state.calibration.loadedCalibration);
    const groundAligned = calibration?.metadata?.groundplane_applied === true;

    return <>
        <SettingsGroupHeading text="Reference frame" info={REFERENCE_FRAME_INFO}/>

        <SettingRow label="Ground plane" info={GROUND_PLANE_INFO}
            control={<span className={`reference-frame-status${groundAligned ? ' reference-frame-status-aligned' : ''}`}
                role="status" aria-label="Calibration ground plane status">
                <span className="reference-frame-status-source">Calibration</span>
                <strong>{groundAligned ? 'Ground plane aligned' : calibration ? 'No saved ground plane' : 'Not loaded'}</strong>
            </span>}/>

        <SettingRow label="Align to person" info={ALIGN_INFO}
            control={<SettingToggleSwitch label="Align to person" isToggled={!groundAligned && enabled}
                disabled={groundAligned} onToggle={value => dispatch(bodyAlignmentUpdated(value))}/>}/>

        <SettingRow label="Custom transformation" info={TRANSFORM_INFO}
            control={<SettingToggleSwitch label="Apply custom transformation" isToggled={transformEnabled}
                onToggle={setTransformEnabled}/>}/>

        {/* The definition and its editor are shown unconditionally. The switch
            above decides whether the transform is applied, never whether the
            feature can be found. */}
        <div className={`reference-transform-block${transformEnabled ? '' : ' reference-transform-block-inactive'}`}>
            <output className="reference-transform-summary" aria-label="Defined transformation">
                {fields
                    ? <>
                        <span><span className="reference-transform-term">q (wxyz)</span>[{preview(fields.slice(3))}]</span>
                        <span><span className="reference-transform-term">t (xyz) mm</span>[{preview(fields.slice(0, 3))}]</span>
                    </>
                    : <span className="reference-transform-identity">Identity — no additional transformation defined</span>}
            </output>
            <div className="reference-transform-actions">
                {transformation && <ButtonSm text="Reset" className="secondary reference-frame-edit"
                    onClick={() => setTransformation(null)}/>}
                <ButtonSm text={transformation ? 'Edit transformation…' : 'Define transformation…'}
                    className="secondary reference-frame-edit" textColor="text-white" onClick={() => setEditorOpen(true)}/>
            </div>
        </div>

        {editorOpen && <TransformEditor initialMatrix={transformation ?? new Matrix4()}
            onAccept={matrix => {setTransformation(matrix); setTransformEnabled(true); setEditorOpen(false);}}
            onClose={() => setEditorOpen(false)}/>}
    </>;
}
