import { initTRPC } from '@trpc/server';
import { z } from 'zod';
import superjson from 'superjson';

// Services
import { PythonServer } from './services/python-server';
import { dialog, shell, app } from 'electron';
import path from 'node:path';
import fs from 'node:fs';
import { APP_PATHS } from './app-paths';

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

        // Look for files matching pattern: *_camera_calibration.toml
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
                    // Check if directory exists
                    result.exists = fs.existsSync(input.directoryPath);

                    if (!result.exists) {
                        // Directory doesn't exist - can record here (will be created)
                        result.canRecord = true;
                        result.canCalibrate = false;
                        return result;
                    }

                    // Directory exists - check its contents
                    const stats = fs.statSync(input.directoryPath);

                    if (!stats.isDirectory()) {
                        result.errorMessage = 'Path exists but is not a directory';
                        return result;
                    }

                    // Check for synchronized_videos folder
                    const synchronizedVideosPath = path.join(input.directoryPath, 'synchronized_videos');
                    result.hasSynchronizedVideos = fs.existsSync(synchronizedVideosPath) &&
                        fs.statSync(synchronizedVideosPath).isDirectory();

                    // Check for videos in synchronized_videos folder
                    if (result.hasSynchronizedVideos) {
                        result.hasVideos = hasVideoFiles(synchronizedVideosPath);
                    }

                    // If no synchronized_videos, check for videos in root directory
                    if (!result.hasVideos) {
                        result.hasVideos = hasVideoFiles(input.directoryPath);
                    }

                    // Determine if we can record
                    // Can record if directory is empty or only has non-video files
                    const entries = fs.readdirSync(input.directoryPath);
                    result.canRecord = entries.length === 0 || !result.hasVideos;

                    // Can calibrate if we have videos
                    result.canCalibrate = result.hasVideos;

                    // Look for camera calibration TOML file
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
                    // Check if directory exists
                    result.exists = fs.existsSync(input.directoryPath);

                    if (!result.exists) {
                        // Directory doesn't exist - can record here (will be created)
                        result.canRecord = true;
                        result.canProcess = false;
                        return result;
                    }

                    // Directory exists - check its contents
                    const stats = fs.statSync(input.directoryPath);

                    if (!stats.isDirectory()) {
                        result.errorMessage = 'Path exists but is not a directory';
                        return result;
                    }

                    // Check for synchronized_videos folder
                    const synchronizedVideosPath = path.join(input.directoryPath, 'synchronized_videos');
                    result.hasSynchronizedVideos = fs.existsSync(synchronizedVideosPath) &&
                        fs.statSync(synchronizedVideosPath).isDirectory();

                    // Check for videos in synchronized_videos folder
                    if (result.hasSynchronizedVideos) {
                        result.hasVideos = hasVideoFiles(synchronizedVideosPath);
                    }

                    // If no synchronized_videos, check for videos in root directory
                    if (!result.hasVideos) {
                        result.hasVideos = hasVideoFiles(input.directoryPath);
                    }

                    // Determine if we can record
                    // Can record if directory is empty or only has non-video files
                    const entries = fs.readdirSync(input.directoryPath);
                    result.canRecord =  !result.hasVideos;
                    // Look for camera calibration TOML file
                    result.cameraCalibrationTomlPath = findCameraCalibrationToml(input.directoryPath);

                    // Can process if we have videos and a calibration file
                    result.canProcess = result.hasVideos && result.cameraCalibrationTomlPath


                    return result;

                } catch (error) {
                    console.error('Error validating calibration directory:', error);
                    result.errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
                    return result;
                }
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

        // Keep the old method for backward compatibility if needed
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
