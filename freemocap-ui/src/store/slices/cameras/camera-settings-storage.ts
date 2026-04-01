import { CameraConfig, extractConfigSettings } from './cameras-types';

const STORAGE_KEY = 'freemocap-camera-settings';

// What we persist per camera: the user-tunable settings + selection state
export interface PersistedCameraSettings {
    selected: boolean;
    desiredConfig: Partial<CameraConfig>;
}

export type PersistedCameraSettingsMap = Record<string, PersistedCameraSettings>;

export function loadPersistedCameraSettings(): PersistedCameraSettingsMap {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) {
        return {};
    }
    try {
        const parsed: unknown = JSON.parse(raw);
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
            throw new Error(`Expected object in localStorage key "${STORAGE_KEY}", got ${typeof parsed}`);
        }
        return parsed as PersistedCameraSettingsMap;
    } catch (e) {
        // Corrupted data — nuke it and start fresh
        localStorage.removeItem(STORAGE_KEY);
        throw new Error(`Failed to parse persisted camera settings, cleared storage: ${e}`);
    }
}

export function savePersistedCameraSettings(settings: PersistedCameraSettingsMap): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function clearPersistedCameraSettings(): void {
    localStorage.removeItem(STORAGE_KEY);
}

// Build a settings entry from a desired config + selection state
export function buildPersistedEntry(
    desiredConfig: CameraConfig,
    selected: boolean,
): PersistedCameraSettings {
    return {
        selected,
        desiredConfig: extractConfigSettings(desiredConfig),
    };
}
