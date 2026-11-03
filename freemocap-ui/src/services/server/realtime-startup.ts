import {serverClient} from './sdk';
import {RealtimeStartupStatusSchema} from '@/types/realtime-startup';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

export class StartupStatusUnavailableError extends Error {
    constructor() {super('Startup status unavailable from this server version');}
}

/** A missing capability is remembered until a different server or reconnect. */
export class StartupStatusCapability {
    private unavailableIdentity: string | null = null;
    allows(identity: string): boolean {return this.unavailableIdentity !== identity;}
    markUnavailable(identity: string): void {this.unavailableIdentity = identity;}
    reset(): void {this.unavailableIdentity = null;}
}

export async function requestRealtimeStartup(signal?: AbortSignal) {
    const response = await serverClient().responses.realtime_startup_status({signal});
    if (response.status === 404) throw new StartupStatusUnavailableError();
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return RealtimeStartupStatusSchema.parse(await response.json());
}

export async function stopRealtimeStartup(signal?: AbortSignal) {
    const response = await serverClient().responses.stop_realtime_startup({signal});
    if (response.status === 404) throw new StartupStatusUnavailableError();
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return RealtimeStartupStatusSchema.parse(await response.json());
}
