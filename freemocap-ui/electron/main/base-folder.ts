import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {app} from 'electron';

/**
 * Single source of truth for the FreeMoCap base data folder.
 *
 * The base data folder (default `~/freemocap_data`) holds every file FreeMoCap writes:
 * recordings, calibrations, logs, telemetry config, etc. The user can relocate it via the
 * Settings page.
 *
 * The *pointer* to that folder cannot live inside the folder itself (the folder is movable), so
 * it is persisted in Electron's OS-standard per-app config directory (`app.getPath('userData')`):
 *   - Windows: %APPDATA%/freemocap
 *   - macOS:   ~/Library/Application Support/freemocap
 *   - Linux:   ~/.config/freemocap
 * This is the only piece of FreeMoCap state that lives outside the base data folder.
 *
 * The resolved path is distributed to the two other processes that need it:
 *   - the Python server, via the FREEMOCAP_BASE_FOLDER env var (see python-server.ts)
 *   - the renderer, via the `fileSystem.getBaseDataFolder` tRPC query (see api.ts)
 */

/** The one definition of the default data-folder name on the TypeScript side. */
export const FREEMOCAP_DATA_DEFAULT_DIRNAME = 'freemocap_data';

/** Env var the Python server reads to discover the base folder. Matches default_paths.py. */
export const FREEMOCAP_BASE_FOLDER_ENV_VAR = 'FREEMOCAP_BASE_FOLDER';

const CONFIG_FILE_NAME = 'freemocap-config.json';
const BASE_FOLDER_KEY = 'baseDataFolder';

function getConfigFilePath(): string {
    return path.join(app.getPath('userData'), CONFIG_FILE_NAME);
}

function getDefaultBaseDataFolder(): string {
    return path.join(os.homedir(), FREEMOCAP_DATA_DEFAULT_DIRNAME);
}

/**
 * The current base data folder: the user's persisted choice, or the default if none is set.
 * Absent/unreadable config is the expected first-run state — we return the default and log.
 */
export function getBaseDataFolder(): string {
    const configPath = getConfigFilePath();
    try {
        if (fs.existsSync(configPath)) {
            const parsed: unknown = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                const stored = (parsed as Record<string, unknown>)[BASE_FOLDER_KEY];
                if (typeof stored === 'string' && stored.trim().length > 0) {
                    return stored;
                }
            }
        }
    } catch (err) {
        console.error(`Failed to read base-folder config at ${configPath}, using default:`, err);
    }
    return getDefaultBaseDataFolder();
}

/** Persist the user's chosen base data folder. */
export function setBaseDataFolder(dir: string): void {
    if (typeof dir !== 'string' || dir.trim().length === 0) {
        throw new Error(`Invalid base data folder path: ${JSON.stringify(dir)}`);
    }

    const configPath = getConfigFilePath();
    fs.mkdirSync(path.dirname(configPath), {recursive: true});

    let existing: Record<string, unknown> = {};
    if (fs.existsSync(configPath)) {
        try {
            const parsed: unknown = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                existing = parsed as Record<string, unknown>;
            }
        } catch (err) {
            console.error(`Overwriting unreadable base-folder config at ${configPath}:`, err);
        }
    }

    existing[BASE_FOLDER_KEY] = dir;
    fs.writeFileSync(configPath, JSON.stringify(existing, null, 2) + '\n', 'utf-8');
}

/** Clear the base-folder override so it reverts to the default `~/freemocap_data`. */
export function resetBaseDataFolder(): void {
    const configPath = getConfigFilePath();
    if (!fs.existsSync(configPath)) return;

    let existing: Record<string, unknown> = {};
    try {
        const parsed: unknown = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            existing = parsed as Record<string, unknown>;
        }
    } catch (err) {
        console.error(`Overwriting unreadable base-folder config at ${configPath}:`, err);
    }

    delete existing[BASE_FOLDER_KEY];
    fs.writeFileSync(configPath, JSON.stringify(existing, null, 2) + '\n', 'utf-8');
}
