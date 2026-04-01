
import { app, BrowserWindow } from 'electron';
import pkg from 'electron-updater';
const { autoUpdater } = pkg;

const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000; // 4 hours
const INITIAL_CHECK_DELAY_MS = 10 * 1000; // 10 seconds after startup

export class UpdateHandler {
    private static instance: UpdateHandler | null = null;
    private checkInterval: ReturnType<typeof setInterval> | null = null;
    private initialTimeout: ReturnType<typeof setTimeout> | null = null;

    private constructor(private mainWindow: BrowserWindow) {
        this.setupEventForwarding();
        this.scheduleChecks();
    }

    private setupEventForwarding() {
        autoUpdater.on('checking-for-update', () => {
            console.log('[AutoUpdater] Checking for updates...');
        });

        autoUpdater.on('update-available', (info) => {
            console.log('[AutoUpdater] Update available:', info.version);
            this.mainWindow.webContents.send('update-available', {
                version: info.version,
                currentVersion: app.getVersion(),
            });
        });

        autoUpdater.on('update-not-available', () => {
            console.log('[AutoUpdater] Already up to date');
        });

        autoUpdater.on('download-progress', (progress) => {
            this.mainWindow.webContents.send('download-progress', progress);
        });

        autoUpdater.on('update-downloaded', (info) => {
            console.log('[AutoUpdater] Update downloaded:', info.version);
            this.mainWindow.webContents.send('update-downloaded', {
                version: info.version,
            });
        });

        autoUpdater.on('error', (error) => {
            console.error('[AutoUpdater] Error:', error.message);
            this.mainWindow.webContents.send('update-error', {
                message: error.message,
            });
        });
    }

    private scheduleChecks() {
        // Initial check after a short delay to let the app finish loading
        this.initialTimeout = setTimeout(() => {
            autoUpdater.checkForUpdates().catch((err) => {
                console.error('[AutoUpdater] Initial check failed:', err.message);
            });
        }, INITIAL_CHECK_DELAY_MS);

        // Periodic checks
        this.checkInterval = setInterval(() => {
            autoUpdater.checkForUpdates().catch((err) => {
                console.error('[AutoUpdater] Periodic check failed:', err.message);
            });
        }, CHECK_INTERVAL_MS);
    }

    dispose() {
        if (this.initialTimeout) clearTimeout(this.initialTimeout);
        if (this.checkInterval) clearInterval(this.checkInterval);
        this.initialTimeout = null;
        this.checkInterval = null;
    }

    static initialize(window: BrowserWindow) {
        UpdateHandler.instance = new UpdateHandler(window);
        return UpdateHandler.instance;
    }

    static shutdown() {
        UpdateHandler.instance?.dispose();
        UpdateHandler.instance = null;
    }
}
