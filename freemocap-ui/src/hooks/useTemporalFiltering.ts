import {useCallback, useEffect} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {applyTemporalConfig, fetchTemporalConfig, pipelineConfigUpdated} from '@/store/slices/realtime';
import {sameTemporalConfig, type TemporalConfig} from '@/types/temporal-config';
import {store} from '@/store';

export function useTemporalFiltering() {
    const dispatch = useAppDispatch();
    const serverConnected = useAppSelector(state => state.connection.isConnected);
    const realtime = useAppSelector(state => state.realtime);
    const pending = Boolean(realtime.temporalStatus?.requested && !sameTemporalConfig(
        realtime.temporalStatus.requested, realtime.temporalStatus.applied,
    ));
    useEffect(() => {
        if (serverConnected) void dispatch(fetchTemporalConfig());
    }, [dispatch, serverConnected, realtime.isConnected]);
    useEffect(() => {
        if (!serverConnected || !pending || realtime.temporalError) return;
        const timer = window.setTimeout(() => { void dispatch(fetchTemporalConfig()); }, 500);
        return () => window.clearTimeout(timer);
    }, [dispatch, serverConnected, pending, realtime.temporalStatus, realtime.temporalError]);
    const apply = useCallback(async (config: TemporalConfig) => {
        const current = store.getState().realtime;
        if (current.isConnected) await dispatch(applyTemporalConfig(config)).unwrap();
        else dispatch(pipelineConfigUpdated({...current.pipelineConfig, aggregator_config: {
            ...current.pipelineConfig.aggregator_config, realtime_filter_config: config,
        }}));
    }, [dispatch]);
    return {config: realtime.pipelineConfig.aggregator_config.realtime_filter_config,
        status: realtime.temporalStatus, pending, apply, isConnected: realtime.isConnected,
        loading: realtime.temporalLoading, error: realtime.temporalError,
        retry: () => dispatch(fetchTemporalConfig())};
}
