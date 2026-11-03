import {createHttpClient} from '@freemocap/client/http';
import {EXECUTION_PROVIDERS, type ExecutionProviderName} from '@/types/execution-provider';

export async function requestExecutionProviders(baseUrl: string, signal?: AbortSignal,
    request: typeof fetch = fetch): Promise<ExecutionProviderName[]> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses.get_available_execution_providers_freemocap_onnx_execution_providers_get({signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.available) || data.available.some((value: unknown) =>
        typeof value !== 'string' || (value !== 'trt' && !EXECUTION_PROVIDERS.some(option => option.value === value)))) {
        throw new Error('Invalid provider response');
    }
    return data.available.filter((value: string) => value !== 'trt');
}

export function executionProviderOptions(selected: ExecutionProviderName | null,
    available: readonly ExecutionProviderName[]) {
    return EXECUTION_PROVIDERS.filter(({value}) => value === null || value === selected || available.includes(value));
}
