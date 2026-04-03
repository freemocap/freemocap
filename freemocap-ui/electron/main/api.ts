
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
// Helper function to check if a directory contains video files
function hasVideoFiles(dirPath: string): boolean {
    if (!fs.existsSync(dirPath)) {
        return false;
    }

    try {
        const entries = fs.readdirSync(dirPath);
        const videoExtensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'];

        return entries.some(entry => {
            const fullPath = path.join(dirPath, entry);
            const stats = fs.statSync(fullPath);

            if (stats.isFile()) {
                const ext = path.extname(entry).toLowerCase();
                return videoExtensions.includes(ext);
            }
            return false;
        });
    } catch (error) {
        console.error('Error checking for video files:', error);
        return false;
    }
}

// Helper function to find camera calibration TOML file
function findCameraCalibrationToml(dirPath: string): string | null {
    if (!fs.existsSync(dirPath)) {
        return null;
    }

    try {
        const entries = fs.readdirSync(dirPath);

        const calibrationFile = entries.find(entry => {
            const fullPath = path.join(dirPath, entry);
            const stats = fs.statSync(fullPath);

            return stats.isFile() &&
                entry.endsWith('_camera_calibration.toml');
        });

        return calibrationFile ? path.join(dirPath, calibrationFile) : null;
    } catch (error) {
        console.error('Error finding calibration TOML:', error);
        return null;
    }
}

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


        validateCalibrationDirectory: t.procedure
            .input(z.object({ directoryPath: z.string() }))
            .query(({ input }) => {
                const result = {
                    exists: false,
                    canRecord: false,
                    canCalibrate: false,
                    cameraCalibrationTomlPath: null as string | null,
                    hasSynchronizedVideos: false,
                    hasVideos: false,
                    errorMessage: null as string | null,
                };

                try {
                    result.exists = fs.existsSync(input.directoryPath);

                    if (!result.exists) {
                        result.canRecord = true;
                        result.canCalibrate = false;
                        return result;
                    }

                    const stats = fs.statSync(input.directoryPath);

                    if (!stats.isDirectory()) {
                        result.errorMessage = 'Path exists but is not a directory';
                        return result;
                    }

                    const synchronizedVideosPath = path.join(input.directoryPath, 'synchronized_videos');
                    result.hasSynchronizedVideos = fs.existsSync(synchronizedVideosPath) &&
                        fs.statSync(synchronizedVideosPath).isDirectory();

                    if (result.hasSynchronizedVideos) {
                        result.hasVideos = hasVideoFiles(synchronizedVideosPath);
                    }

                    if (!result.hasVideos) {
                        result.hasVideos = hasVideoFiles(input.directoryPath);
                    }

                    const entries = fs.readdirSync(input.directoryPath);
                    result.canRecord = entries.length === 0 || !result.hasVideos;

                    result.canCalibrate = result.hasVideos;

                    result.cameraCalibrationTomlPath = findCameraCalibrationToml(input.directoryPath);

                    return result;

                } catch (error) {
                    console.error('Error validating calibration directory:', error);
                    result.errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
                    return result;
                }
            }),

        validateMocapDirectory: t.procedure
            .input(z.object({ directoryPath: z.string() }))
            .query(({ input }) => {
                const result = {
                    exists: false,
                    canRecord: false,
                    canProcess: false,
                    cameraCalibrationTomlPath: null as string | null,
                    hasSynchronizedVideos: false,
                    hasVideos: false,
                    errorMessage: null as string | null,
                };

                try {
                    result.exists = fs.existsSync(input.directoryPath);

                    if (!result.exists) {
                        result.canRecord = true;
                        result.canProcess = false;
                        return result;
                    }

                    const stats = fs.statSync(input.directoryPath);

                    if (!stats.isDirectory()) {
                        result.errorMessage = 'Path exists but is not a directory';
                        return result;
                    }

                    const synchronizedVideosPath = path.join(input.directoryPath, 'synchronized_videos');
                    result.hasSynchronizedVideos = fs.existsSync(synchronizedVideosPath) &&
                        fs.statSync(synchronizedVideosPath).isDirectory();

                    if (result.hasSynchronizedVideos) {
                        result.hasVideos = hasVideoFiles(synchronizedVideosPath);
                    }

                    if (!result.hasVideos) {
                        result.hasVideos = hasVideoFiles(input.directoryPath);
                    }

                    const entries = fs.readdirSync(input.directoryPath);
                    result.canRecord = !result.hasVideos;
                    result.cameraCalibrationTomlPath = findCameraCalibrationToml(input.directoryPath);

                    result.canProcess = result.hasVideos && result.cameraCalibrationTomlPath !== null;

                    return result;

                } catch (error) {
                    console.error('Error validating calibration directory:', error);
                    result.errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
                    return result;
                }
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
                    if (fs.existsSync(APP_PATHS.FREEMOCAP_LOGO_PNG_SHARED_PATH)) {
                        logoPath = APP_PATHS.FREEMOCAP_LOGO_PNG_SHARED_PATH;
                    } else if (fs.existsSync(APP_PATHS.FREEMOCAP_LOGO_PNG_RESOURCES_PATH)) {
                        logoPath = APP_PATHS.FREEMOCAP_LOGO_PNG_RESOURCES_PATH;
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
                if (fs.existsSync(APP_PATHS.FREEMOCAP_LOGO_PNG_SHARED_PATH)) {
                    return APP_PATHS.FREEMOCAP_LOGO_PNG_SHARED_PATH;
                }
                return APP_PATHS.FREEMOCAP_LOGO_PNG_RESOURCES_PATH;
            }),
    }),
});

// Export the type for use in renderer
export type AppAPI = typeof api;
