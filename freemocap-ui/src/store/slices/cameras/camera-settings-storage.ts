import {CameraConfig, DEFAULT_CAMERA_FRAMERATE, extractConfigSettings} from './cameras-types';

const STORAGE_KEY = 'freemocap-camera-settings';

// Version 2 entries were written after the frame-rate control existed.
// Earlier entries could only have stored the old automatic default (-1).
const CURRENT_SETTINGS_VERSION = 2;

// What we persist per camera: the user-tunable settings + selection state
export interface PersistedCameraSettings {
    selected: boolean;
    realtimeEnabled: boolean;
    desiredConfig: Partial<CameraConfig>;
    settingsVersion?: number;
}

export type PersistedCameraSettingsMap = Record<string, PersistedCameraSettings>;

// Replace the old implicit automatic frame rate, which users could not choose,
// with the explicit default. Automatic rates chosen in version 2 are preserved.
export function migratePersistedCameraSettings(settings: PersistedCameraSettingsMap): PersistedCameraSettingsMap {
    const migrated: PersistedCameraSettingsMap = {};
    for (const [cameraId, entry] of Object.entries(settings)) {
        if ((entry.settingsVersion ?? 1) >= CURRENT_SETTINGS_VERSION) {
            migrated[cameraId] = entry;
            continue;
        }
        const framerate = entry.desiredConfig?.framerate;
        migrated[cameraId] = {
            ...entry,
            desiredConfig: {
                ...entry.desiredConfig,
                framerate: framerate === undefined || framerate <= 0 ? DEFAULT_CAMERA_FRAMERATE : framerate,
            },
            settingsVersion: CURRENT_SETTINGS_VERSION,
        };
    }
    return migrated;
}

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
        return migratePersistedCameraSettings(parsed as PersistedCameraSettingsMap);
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
    realtimeEnabled: boolean,
): PersistedCameraSettings {
    return {
        selected,
        realtimeEnabled,
        desiredConfig: extractConfigSettings(desiredConfig),
        settingsVersion: CURRENT_SETTINGS_VERSION,
    };
}
