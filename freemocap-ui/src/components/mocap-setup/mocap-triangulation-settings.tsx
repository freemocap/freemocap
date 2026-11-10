import CameraMatchingSettings from './camera-matching-settings';
import {OutlierRejectionRows} from './outlier-rejection-rows';
import {cameraMatchingUpdated} from '@/store/slices/mocap';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {triangulationConfigUpdated, selectMocapTriangulationConfig} from '@/store/slices/mocap';

export default function TriangulationSettings() {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectMocapTriangulationConfig);
    const matching = useAppSelector(state => state.mocap.config.cameraMatching);

    return <>
        <CameraMatchingSettings config={matching} showFailurePolicy={true}
            onChange={value => dispatch(cameraMatchingUpdated(value))}/>

        <OutlierRejectionRows config={config} onChange={value => dispatch(triangulationConfigUpdated(value))}/>
    </>;
}
