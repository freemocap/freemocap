import {serverClient} from './sdk';
import {TemporalStatusSchema, type TemporalConfig} from '@/types/temporal-config';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

/** A filter update never sends camera settings or creates a pipeline. */
export async function requestTemporalSettings(config?: TemporalConfig) {
    const client = serverClient();
    const response = config ? await client.responses.update_temporal_config_freemocap_realtime_filter_config_put({body: config})
        : await client.responses.temporal_config_status_freemocap_realtime_filter_config_get();
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return TemporalStatusSchema.parse(await response.json());
}
