export const STORAGE_KEYS = {
    SELECTED_EXE_PATH: 'freemocap:selectedExePath',
    PANEL_EXPANDED: 'freemocap:serverPanelExpanded',
    AUTO_LAUNCH_SERVER: 'freemocap:autoLaunchServer',
    AUTO_CONNECT_WS: 'freemocap:autoConnectWs',
    SERVER_HOST: 'freemocap:serverHost',
    SERVER_PORT: 'freemocap:serverPort',
} as const;

export function loadFromStorage<T>(key: string, fallback: T): T {
    try {
        const raw = localStorage.getItem(key);
        if (raw === null) return fallback;
        return JSON.parse(raw) as T;
    } catch {
        return fallback;
    }
}

export function saveToStorage(key: string, value: unknown): void {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (err) {
        console.error(`Failed to save ${key} to localStorage:`, err);
    }
}
