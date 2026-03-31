
import { initTRPC } from '@trpc/server';
import { z } from 'zod';
import superjson from 'superjson';

// Services
import { PythonServer } from './services/python-server';
import { dialog, shell, app } from 'electron';
import pkg from 'electron-updater';
const { autoUpdater } = pkg;
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { APP_PATHS } from './app-paths';

// Configure auto-updater (user triggers download manually)
autoUpdater.autoDownload = false;
autoUpdater.allowDowngrade = false;

// Initialize tRPC
const t = initTRPC.create({
    transformer: superjson, // Handles Date/undefined/etc serialization
});

// Telemetry config lives in ~/freemocap_data/telemetry_config.json
const TELEMETRY_CONFIG_PATH = path.join(os.homedir(), 'freemocap_data', 'telemetry_config.json');

interface TelemetryConfig {
    telemetry_enabled: boolean;
}

function readTelemetryConfig(): TelemetryConfig {
    try {
        if (fs.existsSync(TELEMETRY_CONFIG_PATH)) {
            const raw = fs.readFileSync(TELEMETRY_CONFIG_PATH, 'utf-8');
            const parsed = JSON.parse(raw);
            return { telemetry_enabled: Boolean(parsed.telemetry_enabled) };
        }
    } catch (err) {
        console.error('Failed to read telemetry config:', err);
    }
    // Default: enabled
    return { telemetry_enabled: true };
}

function writeTelemetryConfig(config: TelemetryConfig): void {
    const dir = path.dirname(TELEMETRY_CONFIG_PATH);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(TELEMETRY_CONFIG_PATH, JSON.stringify(config, null, 2) + '\n');
}

// Create the main API router
export const api = t.router({
    // Python Server Management
    pythonServer: t.router({
        start: t.procedure
            .input(z.object({ exePath: z.string().nullable() }))
            .mutation(({ input }) => PythonServer.start(input.exePath)),

        stop: t.procedure
            .mutation(() => PythonServer.shutdown()),

        getExecutablePath: t.procedure
            .query(() => PythonServer.getCurrentExecutablePath()),

        getExecutableCandidates: t.procedure
            .query(() => PythonServer.validateAllCandidates()),

        refreshCandidates: t.procedure
            .mutation(() => PythonServer.refreshCandidates()),

        isRunning: t.procedure
            .query(() => PythonServer.isRunning()),

        getProcessInfo: t.procedure
            .query(() => PythonServer.getProcessInfo()),
    }),

    // File System Operations
    fileSystem: t.router({
        selectDirectory: t.procedure
            .mutation(async () => {
                const result = await dialog.showOpenDialog({
                    properties: ['openDirectory'],
                });
                return result.canceled ? null : result.filePaths[0];
            }),

        openFolder: t.procedure
            .input(z.object({ path: z.string() }))
            .mutation(async ({ input }) => {
                await shell.openPath(input.path);
                return true;
            }),

        getHomeDirectory: t.procedure
            .query(() => app.getPath('home')),

        getFolderContents: t.procedure
            .input(z.object({ path: z.string() }))
            .query(({ input }) => {
                if (!fs.existsSync(input.path)) {
                    throw new Error('Folder does not exist');
                }

                const entries = fs.readdirSync(input.path);
                return entries.map(entry => {
                    const fullPath = path.join(input.path, entry);
                    const stats = fs.statSync(fullPath);
                    return {
                        name: entry,
                        path: fullPath,
                        isDirectory: stats.isDirectory(),
                        isFile: stats.isFile(),
                        size: stats.size,
                        modified: stats.mtime,
                    };
                });
            }),

        selectExecutableFile: t.procedure
            .mutation(async () => {
                const result = await dialog.showOpenDialog({
                    properties: ['openFile'],
                    filters: [
                        { name: 'Executable Files', extensions: ['exe'] },
                        { name: 'All Files', extensions: ['*'] },
                    ],
                });
                return result.canceled ? null : result.filePaths[0];
            }),
    }),

    // Telemetry Settings
    telemetry: t.router({
        getEnabled: t.procedure
            .query((): boolean => {
                return readTelemetryConfig().telemetry_enabled;
            }),

        setEnabled: t.procedure
            .input(z.object({ enabled: z.boolean() }))
            .mutation(({ input }): boolean => {
                writeTelemetryConfig({ telemetry_enabled: input.enabled });
                return input.enabled;
            }),
    }),

    // App Info & Updates
    app: t.router({
        getVersion: t.procedure
            .query((): string => {
                return app.getVersion();
            }),

        checkForUpdate: t.procedure
            .mutation(async () => {
                if (!app.isPackaged) {
                    return { available: false, reason: 'dev-mode' };
                }
                try {
                    const result = await autoUpdater.checkForUpdates();
                    if (result && result.updateInfo) {
                        return {
                            available: result.updateInfo.version !== app.getVersion(),
                            version: result.updateInfo.version,
                            currentVersion: app.getVersion(),
                        };
                    }
                    return { available: false };
                } catch (error) {
                    console.error('[AutoUpdater] Check failed:', error);
                    return { available: false, error: String(error) };
                }
            }),

        downloadUpdate: t.procedure
            .mutation(async () => {
                await autoUpdater.downloadUpdate();
                return true;
            }),

        installUpdate: t.procedure
            .mutation(() => {
                autoUpdater.quitAndInstall(false, true);
            }),
    }),

    // Asset Management
    assets: t.router({
        getLogoBase64: t.procedure
            .query((): string | null => {
                try {
                    let logoPath: string | null = null;

                    // Check for logo in order of preference
                    if (fs.existsSync(APP_PATHS.SKELLYCAM_LOGO_PNG_SHARED_PATH)) {
                        logoPath = APP_PATHS.SKELLYCAM_LOGO_PNG_SHARED_PATH;
                    } else if (fs.existsSync(APP_PATHS.SKELLYCAM_LOGO_PNG_RESOURCES_PATH)) {
                        logoPath = APP_PATHS.SKELLYCAM_LOGO_PNG_RESOURCES_PATH;
                    }

                    if (!logoPath) {
                        console.error('Logo file not found in any expected location');
                        return null;
                    }

                    // Read the file and convert to base64
                    const imageBuffer = fs.readFileSync(logoPath);
                    const base64String = imageBuffer.toString('base64');
                    const mimeType = 'image/png'; // Since we know it's a PNG

                    // Return as a data URL that can be used directly in img src
                    return `data:${mimeType};base64,${base64String}`;
                } catch (error) {
                    console.error('Failed to load logo as base64:', error);
                    return null;
                }
            }),

        getLogoPngPath: t.procedure
            .query(() => {
                if (fs.existsSync(APP_PATHS.SKELLYCAM_LOGO_PNG_SHARED_PATH)) {
                    return APP_PATHS.SKELLYCAM_LOGO_PNG_SHARED_PATH;
                }
                return APP_PATHS.SKELLYCAM_LOGO_PNG_RESOURCES_PATH;
            }),
    }),
});

// Export the type for use in renderer
export type AppAPI = typeof api;
