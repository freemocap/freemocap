import CameraMatchingSettings from './camera-matching-settings';
import {cameraMatchingUpdated} from '@/store/slices/mocap';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {triangulationConfigUpdated, selectMocapTriangulationConfig} from '@/store/slices/mocap';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import DependentRowGroup from '@/components/common/settings-layout/dependent-row-group';

const OUTLIER_INFO = {
    title: "Outlier rejection",
    text: <>
        <p>Evaluates camera subsets and combines their 3D estimates, giving more weight to subsets with lower reprojection error.</p>
        <p>Subsets respect <strong>minimum cameras</strong> and <strong>maximum cameras to drop</strong>.</p>
    </>,
};

const MINIMUM_CAMERAS_INFO = {
    title: "Minimum cameras for triangulation",
    text: <>
        <p>The floor that outlier rejection may never drop below. A keypoint seen by fewer cameras than this is left empty rather than triangulated from too few rays.</p>
        <p><em>Two is the geometric minimum for a 3D position; three or more lets rejection discard a bad ray and still solve.</em></p>
    </>,
};

const MAXIMUM_DROP_INFO = {
    title: "Maximum cameras to drop",
    text: <>
        <p>The most rays outlier rejection may discard for a single keypoint, however poorly they fit.</p>
        <p><em>A cap keeps rejection from quietly reducing a well-observed point to the bare minimum number of views.</em></p>
    </>,
};

const REPROJECTION_INFO = {
    title: "Target reprojection error",
    text: <>
        <p>Reprojection error in <strong>undistorted normalized image coordinates</strong>. This controls how strongly low-error camera subsets are favored.</p>
        <p>If the all-camera estimate is already below this target, no subsets are tried. Smaller values favor low-error subsets more strongly.</p>
    </>,
};

export default function TriangulationSettings() {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectMocapTriangulationConfig);
    const matching = useAppSelector(state => state.mocap.config.cameraMatching);
    const rejecting = config.use_outlier_rejection;

    return <>
        <CameraMatchingSettings config={matching} showFailurePolicy={true}
            onChange={value => dispatch(cameraMatchingUpdated(value))}/>

        <SettingRow label="Use outlier rejection" info={OUTLIER_INFO}
            control={<SettingToggleSwitch label="Use outlier rejection" isToggled={rejecting}
                onToggle={use_outlier_rejection => dispatch(triangulationConfigUpdated({use_outlier_rejection}))}/>}/>

        {/* Governed by the switch above: indented, dimmed when off, never hidden. */}
        <DependentRowGroup>
            <SettingRow inactive={!rejecting} label="Minimum cameras for triangulation" info={MINIMUM_CAMERAS_INFO}
                control={<ValueSelector value={config.minimum_cameras_for_triangulation} min={2} max={100}
                    onChange={minimum_cameras_for_triangulation =>
                        dispatch(triangulationConfigUpdated({minimum_cameras_for_triangulation}))}/>}/>
            <SettingRow inactive={!rejecting} label="Maximum cameras to drop" info={MAXIMUM_DROP_INFO}
                control={<ValueSelector value={config.maximum_cameras_to_drop} min={0} max={100}
                    onChange={maximum_cameras_to_drop =>
                        dispatch(triangulationConfigUpdated({maximum_cameras_to_drop}))}/>}/>
            <SettingRow inactive={!rejecting} label="Target reprojection error" info={REPROJECTION_INFO}
                control={<ValueSelector value={config.target_reprojection_error} min={0.001} max={1.0} step={0.01}
                    onChange={target_reprojection_error =>
                        dispatch(triangulationConfigUpdated({target_reprojection_error}))}/>}/>
        </DependentRowGroup>
    </>;
}
