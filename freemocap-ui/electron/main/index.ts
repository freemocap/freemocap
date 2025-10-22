// electron/main/index.ts
import { app, BrowserWindow } from 'electron';
import { setupIPC } from './ipc';
import { WindowManager } from './services/window-manager';
import { PythonServer } from './services/python-server';
// import { UpdateHandler } from './services/update-handler';
import { LifecycleLogger } from './services/logger';
// import os from 'node:os'; // Uncomment if needed for platform-specific checks

// Export environment configuration
export const APP_ENVIRONMENT = {
    IS_DEV: process.env.NODE_ENV === 'development',
    VITE_DEV_SERVER_URL: process.env.VITE_DEV_SERVER_URL,
};


// Platform config
// if (os.release().startsWith('6.1')) app.disableHardwareAcceleration();
if (process.platform === 'win32') app.setAppUserModelId(app.getName());

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        // Someone tried to run a second instance, focus our window instead
        const windows = BrowserWindow.getAllWindows();
        if (windows.length > 0) {
            const window = windows[0];
            if (window.isMinimized()) window.restore();
            window.focus();
        }
    });

    // App lifecycle
    app.whenReady().then(async () => {
        LifecycleLogger.logProcessInfo();
        console.log('App is ready');

        // Setup IPC
        setupIPC();

        // Create window
        const mainWindow = WindowManager.createMainWindow();

        //TODO: Re-enable auto-updates
        // // Initialize auto-updater (only in production)
        // if (!APP_ENVIRONMENT.IS_DEV) {
        //     UpdateHandler.initialize(mainWindow);
        // }

    });

    app.on('window-all-closed', async () => {
        console.log('All windows closed, shutting down...');
        await PythonServer.shutdown();
        app.quit();
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            WindowManager.createMainWindow();
        }
    });

    app.on('before-quit', async (event) => {
        event.preventDefault();
        console.log('App is quitting, cleaning up...');
        await PythonServer.shutdown();
        app.exit(0);
    });
}
