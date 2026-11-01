import {useEffect, useState} from "react";
import {serverUrls} from "@/services";
import {useAppSelector} from "@/store/hooks";
import type {ExecutionProviderName} from "@/types/execution-provider";
import {requestExecutionProviders, executionProviderOptions} from "@/services/server/execution-providers";

/** Query the connected server again after reconnects or server changes. */
export function useExecutionProviderOptions(selected: ExecutionProviderName | null) {
    const {isConnected, serverPid} = useAppSelector(state => state.connection);
    const endpoint = serverUrls.endpoints.onnxExecutionProviders;
    const [loaded, setLoaded] = useState<{key: string; providers: ExecutionProviderName[]} | null>(null);
    const key = `${endpoint}:${serverPid}:${isConnected}`;
    useEffect(() => {
        setLoaded(null);
        if (!isConnected) return;
        const controller = new AbortController();
        requestExecutionProviders(endpoint, controller.signal)
            .then(providers => {
                if (!controller.signal.aborted) setLoaded({key, providers});
            })
            .catch(error => {
                if (!controller.signal.aborted) console.warn("Could not query ONNX providers:", error);
            });
        return () => controller.abort();
    }, [endpoint, isConnected, serverPid, key]);
    const available = loaded?.key === key ? loaded.providers : [];
    // A failed query must not advertise unsupported providers. Keep saved choices visible.
    return executionProviderOptions(selected, available);
}
