import {app, BrowserWindow} from 'electron';
import {update} from './update';
import {IpcManager} from "./helpers/ipc-manager";
import {WindowManager} from "./helpers/window-manager";
import {PythonServer} from "./helpers/python-server";
import {LifecycleLogger} from "./helpers/logger";
import os from "node:os";



// Environment variables that `python` server will use for its lifecycle management
process.env.FREEMOCAP_RUNNING_IN_ELECTRON = 'true';

// Platform config
// Disable GPU Acceleration for Windows 7
if (os.release().startsWith('6.1')) app.disableHardwareAcceleration()
if (process.platform === 'win32') app.setAppUserModelId(app.getName());

// Initialization Sequence
function startApplication() {
    LifecycleLogger.logProcessInfo();
    IpcManager.initialize();

    app.whenReady()
        .then(() => {
            console.log('App is ready')




            const mainWindow = WindowManager.createMainWindow();

            update(mainWindow);
        });
}

// Lifecycle Handlers
app.on('window-all-closed', async () => {
    await PythonServer.shutdown();
    app.quit();
    LifecycleLogger.logShutdownSequence();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        WindowManager.createMainWindow();
    }
});

// Start App
console.log('Starting application');
startApplication();
