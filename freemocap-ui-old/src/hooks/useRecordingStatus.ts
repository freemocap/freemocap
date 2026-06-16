import {useCallback, useEffect} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    fetchRecordingStatus,
    selectRecordingStatusEntry,
} from '@/store/slices/recording-status';

export function useRecordingStatus(
    recordingId: string | null | undefined,
    options: { autoFetch?: boolean; recordingParentDirectory?: string | null } = {}
) {
    const {autoFetch = true, recordingParentDirectory = null} = options;
    const dispatch = useAppDispatch();
    const entry = useAppSelector(selectRecordingStatusEntry(recordingId));

    const refresh = useCallback(() => {
        if (!recordingId) return;
        void dispatch(fetchRecordingStatus({recordingId, recordingParentDirectory}));
    }, [dispatch, recordingId, recordingParentDirectory]);

    // Auto-fetch exactly once per (recordingId) — don't retry on error.
    // If we already have an entry (success OR failure OR in-flight), skip.
    useEffect(() => {
        if (!autoFetch) return;
        if (!recordingId) return;
        if (entry) return;
        refresh();
    }, [autoFetch, recordingId, entry, refresh]);

    return {
        status: entry?.status ?? null,
        isLoading: entry?.isLoading ?? false,
        error: entry?.error ?? null,
        fetchedAt: entry?.fetchedAt ?? null,
        refresh,
    };
}
