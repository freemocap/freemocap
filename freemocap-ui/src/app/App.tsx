import React from 'react';
import {Provider} from 'react-redux';
import {store} from '@/store';
import {ServerContextProvider} from "@/services/server/ServerContextProvider";
import {AppContent} from "@/app/AppContent";

const MetricsServerContextProvider = React.lazy(() => import("@/services/server/MetricsServerContextProvider").then(m => ({default: m.MetricsServerContextProvider})));

function isMetricsRoute(): boolean {
    return typeof window !== 'undefined' && window.location.hash.includes('/pipeline-metrics');
}

function App() {
    const metricsOnly = isMetricsRoute();

    return (
        <Provider store={store}>
            {metricsOnly ? (
                <React.Suspense fallback={<div style={{height:'100vh',backgroundColor:'var(--gray-900)'}} />}>
                    <MetricsServerContextProvider>
                        <AppContent metricsOnly />
                    </MetricsServerContextProvider>
                </React.Suspense>
            ) : (
                <ServerContextProvider>
                    <AppContent />
                </ServerContextProvider>
            )}
        </Provider>
    );
}

export default App;
