import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const FREEMOCAP_CONFIG_DIR = path.join(os.homedir(), '.freemocap');
const SETTINGS_FILE = path.join(FREEMOCAP_CONFIG_DIR, 'settings.json');

type SettingsData = Record<string, unknown>;

function ensureConfigDir(): void {
    if (!fs.existsSync(FREEMOCAP_CONFIG_DIR)) {
        fs.mkdirSync(FREEMOCAP_CONFIG_DIR, { recursive: true });
    }
}

function readAll(): SettingsData {
    ensureConfigDir();
    if (!fs.existsSync(SETTINGS_FILE)) {
        return {};
    }
    const raw = fs.readFileSync(SETTINGS_FILE, 'utf-8');
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error(`Corrupted settings file: expected object, got ${typeof parsed}`);
    }
    return parsed as SettingsData;
}

function writeAll(data: SettingsData): void {
    ensureConfigDir();
    fs.writeFileSync(SETTINGS_FILE, JSON.stringify(data, null, 2), 'utf-8');
}

export class AppSettings {
    /** Get a single value by key. Returns null if the key doesn't exist. */
    static get(key: string): unknown {
        const data = readAll();
        if (!(key in data)) {
            return null;
        }
        return data[key];
    }

    /** Set a single key-value pair. */
    static set(key: string, value: unknown): void {
        const data = readAll();
        data[key] = value;
        writeAll(data);
    }

    /** Delete a single key. */
    static delete(key: string): void {
        const data = readAll();
        if (!(key in data)) {
            return;
        }
        delete data[key];
        writeAll(data);
    }

    /** Get all settings as a plain object. */
    static getAll(): SettingsData {
        return readAll();
    }

    /** Replace all settings with the given object. */
    static setAll(data: SettingsData): void {
        writeAll(data);
    }

    /** Get the path to the config directory (~/.freemocap/). */
    static getConfigDir(): string {
        ensureConfigDir();
        return FREEMOCAP_CONFIG_DIR;
    }

    /** Get the path to the settings file. */
    static getSettingsFilePath(): string {
        return SETTINGS_FILE;
    }
}
