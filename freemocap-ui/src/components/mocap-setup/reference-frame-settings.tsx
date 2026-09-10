import {useMemo, useState} from 'react';
import {Matrix4} from 'three';
import {useAppDispatch, useAppSelector} from '@/store';
import {
    referenceTransformEnabledUpdated,
    referenceTransformUpdated,
    selectReferenceTransform,
    selectReferenceTransformEnabled,
} from '@/store/slices/mocap';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SettingRow from '@/components/common/settings-layout/setting-row';
import BodyAlignmentSettings from './body-alignment-settings';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import TransformEditor from './transform-editor';
import {transformFields, transformFromFields, TransformRepresentation} from './reference-transform';

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
    return <>
        <BodyAlignmentSettings/>

        <SettingRow label="Apply custom transform" info={TRANSFORM_INFO}
            control={<SettingToggleSwitch label="Apply custom transform" isToggled={transformEnabled}
                onToggle={setTransformEnabled}/>}/>

        {/* The definition and its editor are shown unconditionally. The switch
            above decides whether the transform is applied, never whether the
            feature can be found. */}
        <div className={`reference-transform-block${transformEnabled ? '' : ' reference-transform-block-inactive'}`}>
            {fields && <output className="reference-transform-summary" aria-label="Defined transformation">
                        <span><span className="reference-transform-term">q (wxyz)</span>[{preview(fields.slice(3))}]</span>
                        <span><span className="reference-transform-term">t (xyz) mm</span>[{preview(fields.slice(0, 3))}]</span>
            </output>}
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
    </>;
}

