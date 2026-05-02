const PREFIX = 'freemocap:';

export function loadFromStorage<T>(key: string, fallback: T): T {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(PREFIX + key);
    if (raw === null) return fallback;
    try {
        return JSON.parse(raw) as T;
    } catch {
        localStorage.removeItem(PREFIX + key);
        return fallback;
    }
}

export function saveToStorage<T>(key: string, value: T): void {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
}
