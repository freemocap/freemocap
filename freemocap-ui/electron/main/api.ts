
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
        openSelectDirectoryDialog: t.procedure
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
