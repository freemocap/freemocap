import { app, BrowserWindow } from 'electron';
import { setupIPC } from './ipc';
import { WindowManager } from './services/window-manager';
import { PythonServer } from './services/python-server';
import { buildAppMenu } from './services/app-menu';
import { LifecycleLogger } from './services/logger';

export const APP_ENVIRONMENT = {
    IS_DEV: process.env.NODE_ENV === 'development',
    VITE_DEV_SERVER_URL: process.env.VITE_DEV_SERVER_URL,
};

if (process.platform === 'win32') app.setAppUserModelId(app.getName());

const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        const windows = BrowserWindow.getAllWindows();
        if (windows.length > 0) {
            const window = windows[0];
            if (window.isMinimized()) window.restore();
            window.focus();
        }
    });

    app.whenReady().then(async () => {
        LifecycleLogger.logProcessInfo();
        console.log('App is ready');

        setupIPC();

        const mainWindow = WindowManager.createMainWindow();

        // Set up the native application menu (File, Edit, View, Tools, etc.)
        buildAppMenu(mainWindow);
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
