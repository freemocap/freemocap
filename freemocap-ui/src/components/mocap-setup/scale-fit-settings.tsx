import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {anchorSegmentNameUpdated} from '@/store/slices/mocap/mocap-slice';
import SkeletonAnchorSetting from './skeleton-anchor-setting';

/** Person scale fitting: the body segment that positions the fitted skeleton. */
export default function ScaleFitSettings() {
    const dispatch = useAppDispatch();
    const anchor = useAppSelector(state => state.mocap.config.anchorSegmentName);
    return <SkeletonAnchorSetting value={anchor} onChange={value => dispatch(anchorSegmentNameUpdated(value))}/>;
}
