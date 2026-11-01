import {EXECUTION_PROVIDERS, type ExecutionProviderName} from '@/types/execution-provider';

export async function requestExecutionProviders(endpoint: string, signal?: AbortSignal,
    request: typeof fetch = fetch): Promise<ExecutionProviderName[]> {
    const response = await request(endpoint, {signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.available) || data.available.some((value: unknown) =>
        typeof value !== 'string' || !EXECUTION_PROVIDERS.some(option => option.value === value))) {
        throw new Error('Invalid provider response');
    }
    return data.available;
}

export function executionProviderOptions(selected: ExecutionProviderName | null,
    available: readonly ExecutionProviderName[]) {
    return EXECUTION_PROVIDERS.filter(({value}) => value === null || value === selected || available.includes(value));
}
