import {TemporalStatusSchema, type TemporalConfig} from '@/types/temporal-config';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

/** A filter update never sends camera settings or creates a pipeline. */
export async function requestTemporalSettings(url: string, config?: TemporalConfig) {
    const response = await fetch(url, config ? {
        method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config),
    } : undefined);
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return TemporalStatusSchema.parse(await response.json());
}
