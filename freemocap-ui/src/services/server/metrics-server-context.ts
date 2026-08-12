import {createContext, useContext} from 'react';
import type {PipelineTimingStore} from './server-helpers/pipeline-timing-store';

export interface MetricsServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    getPipelineTimingStore: () => PipelineTimingStore;
}

export const MetricsServerContext = createContext<MetricsServerContextValue | null>(null);

export const useMetricsServer = (): MetricsServerContextValue => {
    const context = useContext(MetricsServerContext);
    if (!context) {
        throw new Error('useMetricsServer must be used within MetricsServerContextProvider');
    }
    return context;
};
