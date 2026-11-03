import {useRealtimeStartup} from '@/hooks/useRealtimeStartup';
import {RealtimeStartupStatusView} from '@/components/control-panels/realtime-panel/RealtimeStartupStatusView';
import {OnnxPreparationView} from '@/components/control-panels/realtime-panel/OnnxPreparationView';
import {useOnnxPreparation} from '@/hooks/useOnnxPreparation';

export function RealtimeStartupBanner() {
    const startup = useRealtimeStartup();
    const preparation = useOnnxPreparation(startup.statusUnavailable ? null : startup.snapshot?.pipeline_id ?? null);
    return <><RealtimeStartupStatusView snapshot={startup.snapshot} statusError={startup.statusError}
        pending={startup.pending} statusUnavailable={startup.statusUnavailable} onStop={startup.stop} onRetry={startup.retry}/>
        <OnnxPreparationView {...preparation}/></>;
}
