import {useId} from 'react';
import {useAppDispatch, useAppSelector} from '@/store';
import {calibrationConfigUpdated} from '@/store/slices/calibration';
import {CalibrationAlignmentMethodSchema} from '@/store/slices/calibration/calibration-types';
import Checkbox from '@/components/ui-components/Checkbox';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import './calibration-alignment-settings.css';

const ALIGN_INFO = {
    title: 'Alignment method',
    text: <>
        <p>Choose one alignment method. ChArUco uses the initial board pose when creating a calibration.</p>
        <p>Person alignment uses observations from mocap processing to transform the supplied points and cameras, regardless of the calibration's previous alignment. It does not modify the calibration file.</p>
        <p>No additional alignment keeps the supplied frame. A configured manual transform applies afterward.</p>
    </>,
};

export default function CalibrationAlignmentSettings({
    allowPerson, disabled = false,
}: {allowPerson: boolean; disabled?: boolean}) {
    const dispatch = useAppDispatch();
    const groupName = useId();
    const method = useAppSelector(state => state.calibration.config.alignmentMethod);
    const methods = CalibrationAlignmentMethodSchema.enum;
    const selectMethod = (alignmentMethod: typeof method) =>
        dispatch(calibrationConfigUpdated({alignmentMethod}));
    if (!allowPerson) {
        return <Checkbox
            label="Align to ChArUco ground plane"
            className="calibration-alignment-checkbox"
            checked={method === methods.charuco}
            disabled={disabled}
            onChange={event => selectMethod(event.target.checked ? methods.charuco : null)}
        />;
    }
    return <>
        <SettingsGroupHeading text="Capture volume alignment" info={ALIGN_INFO}/>
        <fieldset className="calibration-alignment-choices"
            aria-label="Alignment method" disabled={disabled}>
            <label className="calibration-alignment-choice">
                <input type="radio" name={groupName}
                    checked={method === methods.charuco}
                    onChange={() => selectMethod(methods.charuco)}/>
                <span>
                    <span className="calibration-alignment-title">ChArUco ground plane</span>
                    <span className="calibration-alignment-detail">Use the initial board pose when creating calibration.</span>
                </span>
            </label>
            <label className="calibration-alignment-choice">
                <input type="radio" name={groupName}
                    checked={method === methods.person}
                    onChange={() => selectMethod(methods.person)}/>
                <span>
                    <span className="calibration-alignment-title">Align to person</span>
                    <span className="calibration-alignment-detail">Reorient points and cameras during mocap processing.</span>
                </span>
            </label>
            <label className="calibration-alignment-choice">
                <input type="radio" name={groupName}
                    checked={method === null}
                    onChange={() => selectMethod(null)}/>
                <span>
                    <span className="calibration-alignment-title">No additional alignment</span>
                    <span className="calibration-alignment-detail">Keep the supplied calibration frame.</span>
                </span>
            </label>
        </fieldset>
    </>;
}

