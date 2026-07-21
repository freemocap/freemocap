import {initTRPC} from '@trpc/server';
import {z} from 'zod';
import superjson from 'superjson';
import {parse as parseToml} from 'smol-toml';

// Services
import {PythonServer} from './services/python-server';
import {app, dialog, shell} from 'electron';
import pkg from 'electron-updater';
import path from 'node:path';
import fs from 'node:fs';
import {APP_PATHS} from './app-paths';
import {getBaseDataFolder, setBaseDataFolder, resetBaseDataFolder} from './base-folder';

const { autoUpdater } = pkg;

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

function getLastSuccessfulCalibrationPath(): string {
    return path.join(getBaseDataFolder(), 'calibrations', 'last_successful_camera_calibration.toml');
}

function findLastSuccessfulCalibrationToml(): string | null {
    try {
        const calibrationPath = getLastSuccessfulCalibrationPath();
        return fs.existsSync(calibrationPath) ? calibrationPath : null;
    } catch {
        return null;
    }
}

// Telemetry config lives inside the base data folder (default ~/freemocap_data/telemetry_config.json)
function getTelemetryConfigPath(): string {
    return path.join(getBaseDataFolder(), 'telemetry_config.json');
}

interface TelemetryConfig {
    telemetry_enabled: boolean;
}

function readTelemetryConfig(): TelemetryConfig {
    const configPath = getTelemetryConfigPath();
    try {
        if (fs.existsSync(configPath)) {
            const raw = fs.readFileSync(configPath, 'utf-8');
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
    const configPath = getTelemetryConfigPath();
    const dir = path.dirname(configPath);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n');
}

/**
 * Restart the Python server ONLY if Electron launched it. If the server is running from source
 * (standalone / `uv run`), Electron does not own it — we must not touch it; the user restarts it
 * themselves. Returns whether a restart actually happened.
 */
async function restartServerIfOwned(): Promise<boolean> {
    if (!PythonServer.isRunning()) return false;
    const currentExe = PythonServer.getCurrentExecutablePath();
    await PythonServer.shutdown();
    await PythonServer.start(currentExe);
    return true;
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

        getBaseDataFolder: t.procedure
            .query(() => getBaseDataFolder()),

        setBaseDataFolder: t.procedure
            .input(z.object({ path: z.string() }))
            .mutation(async ({ input }) => {
                setBaseDataFolder(input.path);
                const serverRestarted = await restartServerIfOwned();
                return { baseFolder: getBaseDataFolder(), serverRestarted };
            }),

        resetBaseDataFolder: t.procedure
            .mutation(async () => {
                resetBaseDataFolder();
                const serverRestarted = await restartServerIfOwned();
                return { baseFolder: getBaseDataFolder(), serverRestarted };
            }),

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

        readCalibrationToml: t.procedure
            .input(z.object({ path: z.string() }))
            .query(({ input }) => {
                if (!fs.existsSync(input.path)) {
                    throw new Error(`Calibration TOML not found: ${input.path}`);
                }
                const raw = fs.readFileSync(input.path, 'utf-8');
                const parsed = parseToml(raw) as Record<string, any>;
                const mtimeMs = fs.statSync(input.path).mtimeMs;

                const cameras: Array<{
                    id: string;
                    name: string;
                    size: [number, number];
                    matrix: number[][];
                    distortions: number[];
                    rotation: [number, number, number];
                    translation: [number, number, number];
                    world_orientation: number[][];
                    world_position: [number, number, number];
                }> = [];

                for (const [key, val] of Object.entries(parsed)) {
                    if (key === 'metadata' || typeof val !== 'object' || val === null) continue;
                    const c = val as any;
                    if (!Array.isArray(c.world_position) || !Array.isArray(c.world_orientation)) continue;
                    cameras.push({
                        id: key,
                        name: String(c.name ?? key),
                        size: c.size,
                        matrix: c.matrix,
                        distortions: c.distortions,
                        rotation: c.rotation,
                        translation: c.translation,
                        world_orientation: c.world_orientation,
                        world_position: c.world_position,
                    });
                }

                return {
                    path: input.path,
                    mtimeMs,
                    cameras,
                    metadata: (parsed.metadata ?? null) as Record<string, any> | null,
                };
            }),

        selectTomlFile: t.procedure
            .mutation(async () => {
                const result = await dialog.showOpenDialog({
                    properties: ['openFile'],
                    filters: [
                        { name: 'TOML Files', extensions: ['toml'] },
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
                    lastSuccessfulCalibrationTomlPath: null as string | null,
                    hasSynchronizedVideos: false,
                    hasVideos: false,
                    errorMessage: null as string | null,
                };

                try {
                    result.exists = fs.existsSync(input.directoryPath);

                    if (!result.exists) {
                        result.canRecord = true;
                        result.canCalibrate = false;
                        result.lastSuccessfulCalibrationTomlPath = findLastSuccessfulCalibrationToml();
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
                    result.lastSuccessfulCalibrationTomlPath = findLastSuccessfulCalibrationToml();

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
                    canCalibrate: false,
                    canProcess: false,
                    cameraMocapTomlPath: null as string | null,
                    lastSuccessfulCalibrationTomlPath: null as string | null,
                    hasSynchronizedVideos: false,
                    hasVideos: false,
                    errorMessage: null as string | null,
                };

                try {
                    result.exists = fs.existsSync(input.directoryPath);

                    if (!result.exists) {
                        result.canRecord = true;
                        result.canProcess = false;
                        result.lastSuccessfulCalibrationTomlPath = findLastSuccessfulCalibrationToml();
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
                    result.cameraMocapTomlPath = findCameraCalibrationToml(input.directoryPath);
                    result.lastSuccessfulCalibrationTomlPath = findLastSuccessfulCalibrationToml();

                    result.canCalibrate = result.hasVideos && result.cameraMocapTomlPath !== null;

                    result.canProcess = result.hasVideos && result.cameraMocapTomlPath !== null;

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
