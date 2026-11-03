import {useEffect} from 'react';
import {useAppDispatch} from '@/store/hooks';
import {recordingPathCleared, savedStagesRequested} from '@/store/slices/processing-stages';

/**
 * Load the recording's saved stages whenever its owner mounts or the recording changes.
 * Only the newest request updates the store, so overlapping requests cannot overwrite a newer answer.
 */
export function useSavedStageInventory(path: string | null): void {
    const dispatch = useAppDispatch();
    useEffect(() => {
        if (path) void dispatch(savedStagesRequested(path));
        else dispatch(recordingPathCleared());
    }, [dispatch, path]);
}
