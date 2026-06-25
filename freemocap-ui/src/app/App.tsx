import React from 'react';
import {Provider} from 'react-redux';
import {store} from '@/store';
import {ServerContextProvider} from "@/services/server/ServerContextProvider";
import {MetricsServerContextProvider} from "@/services/server/MetricsServerContextProvider";
import {AppContent} from "@/app/AppContent";

function isMetricsRoute(): boolean {
    return typeof window !== 'undefined' && window.location.hash.includes('/pipeline-metrics');
}

function App() {
    const metricsOnly = isMetricsRoute();

    return (
        <Provider store={store}>
            {metricsOnly ? (
                <MetricsServerContextProvider>
                    <AppContent metricsOnly />
                </MetricsServerContextProvider>
            ) : (
                <ServerContextProvider>
                    <AppContent />
                </ServerContextProvider>
            )}
        </Provider>
    );
}

export default App;
