import {isElectron} from '@/services/electron-ipc/electron-ipc';
import {electronIpcClient} from '@/services/electron-ipc/electron-ipc-client';

const METRICS_HASH = '#/pipeline-metrics';

export async function openPipelineMetricsWindow(): Promise<void> {
    if (isElectron()) {
        await electronIpcClient.windows.openPipelineMetrics.mutate();
        return;
    }
    const url = `${window.location.origin}${window.location.pathname}${METRICS_HASH}`;
    const opened = window.open(url, 'freemocap-pipeline-metrics', 'width=1100,height=700');
    opened?.focus();
}
