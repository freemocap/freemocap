import {app, BrowserWindow} from 'electron';
import {update} from './update';
import {IpcManager} from "./helpers/ipc-manager";
import {WindowManager} from "./helpers/window-manager";
import {PythonServer} from "./helpers/python-server";
import {LifecycleLogger} from "./helpers/logger";
import os from "node:os";
import {APP_ENVIRONMENT} from "./helpers/app-environment";
import {installExtension, REDUX_DEVTOOLS} from 'electron-devtools-installer';


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
            const options = {
                loadExtensionOptions: { allowFileAccess: true },
            };
            installExtension(REDUX_DEVTOOLS, options)
                .then((ext) => console.log(`Added Extension:  ${ext.name}`))
                .catch((err) => console.log('An error occurred: ', err));

            console.log('SHOULD_LAUNCH_PYTHON:', APP_ENVIRONMENT.SHOULD_LAUNCH_PYTHON);
            if (APP_ENVIRONMENT.SHOULD_LAUNCH_PYTHON) {
                console.log('Launching Python Server');
                PythonServer.start();
            }

            const mainWindow = WindowManager.createMainWindow();

            // TODO: Add Redux and React DevTools Extensions to Electron App BrowserWindow - the code below didn't work
            // installExtension([REDUX_DEVTOOLS, REACT_DEVELOPER_TOOLS])
            //     .then(([redux, react]) => console.log(`Added Extensions:  ${redux.name}, ${react.name}`))
            //     .catch((err) => console.log('An error occurred: ', err));
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
