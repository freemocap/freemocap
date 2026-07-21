export interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
    resolvedPath?: string;
}

export const AUTO_CONNECT_DELAY_MS = 2000;
export const WS_RECONNECT_INTERVAL_MS = 3000;
