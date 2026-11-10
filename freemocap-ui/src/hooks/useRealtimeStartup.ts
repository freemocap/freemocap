import {useCallback} from 'react';
import {store} from '@/store';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {pipelineErrorReceived} from '@/store/slices/realtime/realtime-slice';
import {stopRealtimeStartup} from '@/services/server/realtime-startup';
import {readStartupWithDeadline} from '@/services/server/startup-polling';
import {describeError} from '@/store/slices/thunk-helpers';

/** Cancellation belongs to the current request. Completed task history never controls this action. */
export function useRealtimeStartup() {
    const dispatch = useAppDispatch();
    const pending = useAppSelector(state => state.realtime.applyPending);
    const stop = useCallback(async () => {
        const requestId = store.getState().realtime.applyRequestId;
        try {
            await readStartupWithDeadline(stopRealtimeStartup, new AbortController().signal);
        } catch (error) {
            if (store.getState().realtime.applyRequestId === requestId) {
                dispatch(pipelineErrorReceived(describeError(error)));
            }
        }
    }, [dispatch]);
    return {pending, stop};
}
