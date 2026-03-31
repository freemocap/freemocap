
import { app, ipcMain, BrowserWindow } from 'electron';
import { autoUpdater } from 'electron-updater';

export class UpdateHandler {
    private mainWindow: BrowserWindow;

    constructor(window: BrowserWindow) {
        this.mainWindow = window;
        this.setupAutoUpdater();
        this.registerIpcHandlers();
    }

    private setupAutoUpdater() {
        autoUpdater.autoDownload = false;
        autoUpdater.disableWebInstaller = false;
        autoUpdater.allowDowngrade = false;

        autoUpdater.on('checking-for-update', () => {
            console.log('Checking for updates...');
        });

        autoUpdater.on('update-available', (info) => {
            console.log('Update available:', info);
            this.mainWindow.webContents.send('update-available', {
                version: info.version,
                currentVersion: app.getVersion(),
            });
        });

        autoUpdater.on('update-not-available', () => {
            console.log('No updates available');
        });

        autoUpdater.on('download-progress', (progress) => {
            this.mainWindow.webContents.send('download-progress', progress);
        });

        autoUpdater.on('update-downloaded', () => {
            this.mainWindow.webContents.send('update-downloaded');
        });

        autoUpdater.on('error', (error) => {
            console.error('Update error:', error);
            this.mainWindow.webContents.send('update-error', error);
        });
    }

    private registerIpcHandlers() {
        ipcMain.handle('check-update', async () => {
            if (!app.isPackaged) {
                return {
                    error: 'Updates only work in packaged app',
                    available: false
                };
            }
            return await autoUpdater.checkForUpdatesAndNotify();
        });

        ipcMain.handle('download-update', async () => {
            return await autoUpdater.downloadUpdate();
        });

        ipcMain.handle('install-update', () => {
            autoUpdater.quitAndInstall(false, true);
        });
    }

    static initialize(window: BrowserWindow) {
        return new UpdateHandler(window);
    }
}
