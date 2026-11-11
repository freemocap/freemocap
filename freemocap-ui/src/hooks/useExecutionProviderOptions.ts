import {useEffect, useState} from "react";
import {serverUrls} from "@/services";
import {EXECUTION_PROVIDERS, ExecutionProviderName} from "@/store/slices/mocap";

// Fetched once per app session; the installed onnxruntime build doesn't change while the server runs.
let availableProvidersPromise: Promise<ExecutionProviderName[]> | null = null;

function fetchAvailableProviders(): Promise<ExecutionProviderName[]> {
    if (!availableProvidersPromise) {
        availableProvidersPromise = fetch(serverUrls.endpoints.onnxExecutionProviders)
            .then((response) => {
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then((data) => data.available as ExecutionProviderName[])
            .catch((e) => {
                availableProvidersPromise = null; // retry on next mount
                throw e;
            });
    }
    return availableProvidersPromise;
}

/**
 * Execution provider choices for the selector: "Auto" plus whichever providers the
 * server's ONNX Runtime install supports. Falls back to every provider if the
 * server can't be queried, and always keeps the currently selected one visible.
 */
export function useExecutionProviderOptions(selected: ExecutionProviderName | null) {
    const [available, setAvailable] = useState<ExecutionProviderName[] | null>(null);

    useEffect(() => {
        let cancelled = false;
        fetchAvailableProviders()
            .then((providers) => { if (!cancelled) setAvailable(providers); })
            .catch((e) => console.warn("Could not query available ONNX execution providers:", e));
        return () => { cancelled = true; };
    }, []);

    return EXECUTION_PROVIDERS.filter(
        ({value}) => value === null || value === selected || available === null || available.includes(value)
    );
}
