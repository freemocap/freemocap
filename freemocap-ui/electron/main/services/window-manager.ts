import {BrowserWindow, shell} from 'electron';
import {LifecycleLogger} from './logger';
import {APP_ENVIRONMENT} from '../index';
import {APP_PATHS} from '../app-paths';

export class WindowManager {
    private static mainWindow: BrowserWindow | null = null;
    private static metricsWindow: BrowserWindow | null = null;

    static createMainWindow(): BrowserWindow {
        if (this.mainWindow && !this.mainWindow.isDestroyed()) {
            return this.mainWindow;
        }

        const window = new BrowserWindow({
            title: 'FreeMoCap 💀📸',
            icon: APP_PATHS.FREEMOCAP_ICON_PATH,
            width: 1280,
            height: 720,
            minWidth: 800,
            minHeight: 600,
            webPreferences: {
                preload: APP_PATHS.PRELOAD,
                contextIsolation: true,
                nodeIntegration: false,
                sandbox: true,
            },
            show: false,
        });

        this.mainWindow = window;
        this.configureWindowHandlers(window);
        this.loadContent(window);

        window.once('ready-to-show', () => {
            window.show();
            LifecycleLogger.logWindowCreation(window);
        });

        return window;
    }

    private static configureWindowHandlers(window: BrowserWindow): void {
        console.log('Configuring window handlers');

        window.on('closed', () => {
            console.log('Window closed');
            if (this.metricsWindow && !this.metricsWindow.isDestroyed()) {
                this.metricsWindow.close();
            }
            this.mainWindow = null;
        });

        window.webContents.on('did-finish-load', () => {
            console.log('Window finished loading');
            window.webContents.send('app-ready', Date.now());
        });

        window.webContents.setWindowOpenHandler(({ url }) => {
            if (url.startsWith('http:') || url.startsWith('https:')) {
                shell.openExternal(url).catch(err =>
                    console.error('Failed to open external link:', err),
                );
            }
            return { action: 'deny' };
        });

        window.webContents.on('will-navigate', (event, url) => {
            if (APP_ENVIRONMENT.IS_DEV && url.startsWith(APP_ENVIRONMENT.VITE_DEV_SERVER_URL!)) {
                return;
            }

            if (!APP_ENVIRONMENT.IS_DEV && url.startsWith('file://')) {
                return;
            }

            if (url.startsWith('http:') || url.startsWith('https:')) {
                event.preventDefault();
                shell.openExternal(url).catch(err =>
                    console.error('Failed to open external link via navigation:', err),
                );
            }
        });

        window.webContents.on('render-process-gone', (event, details) => {
            console.error('Renderer process gone:', details);
            if (details.reason === 'crashed') {
                window.reload();
            }
        });
    }

    private static loadContent(window: BrowserWindow): void {
        console.log('Loading app content - IS_DEV:', APP_ENVIRONMENT.IS_DEV);

        if (APP_ENVIRONMENT.IS_DEV && APP_ENVIRONMENT.VITE_DEV_SERVER_URL) {
            window.loadURL(APP_ENVIRONMENT.VITE_DEV_SERVER_URL);
            // window.webContents.openDevTools();
        } else {
            window.loadFile(APP_PATHS.RENDERER_HTML);
        }
    }

    static getMainWindow(): BrowserWindow | null {
        return this.mainWindow;
    }

    static openMetricsWindow(): BrowserWindow {
        if (this.metricsWindow && !this.metricsWindow.isDestroyed()) {
            this.metricsWindow.focus();
            return this.metricsWindow;
        }

        const window = new BrowserWindow({
            title: 'FreeMoCap Pipeline Metrics',
            icon: APP_PATHS.FREEMOCAP_ICON_PATH,
            width: 1100,
            height: 700,
            minWidth: 640,
            minHeight: 400,
            webPreferences: {
                preload: APP_PATHS.PRELOAD,
                contextIsolation: true,
                nodeIntegration: false,
                sandbox: true,
            },
            show: false,
        });

        this.metricsWindow = window;
        this.configureMetricsWindowHandlers(window);
        this.loadMetricsContent(window);

        window.once('ready-to-show', () => {
            window.show();
        });

        return window;
    }

    private static configureMetricsWindowHandlers(window: BrowserWindow): void {
        window.on('closed', () => {
            this.metricsWindow = null;
        });

        window.webContents.setWindowOpenHandler(({url}) => {
            if (url.startsWith('http:') || url.startsWith('https:')) {
                shell.openExternal(url).catch(err =>
                    console.error('Failed to open external link:', err),
                );
            }
            return {action: 'deny'};
        });

        window.webContents.on('will-navigate', (event, url) => {
            if (APP_ENVIRONMENT.IS_DEV && url.startsWith(APP_ENVIRONMENT.VITE_DEV_SERVER_URL!)) {
                return;
            }
            if (!APP_ENVIRONMENT.IS_DEV && url.startsWith('file://')) {
                return;
            }
            if (url.startsWith('http:') || url.startsWith('https:')) {
                event.preventDefault();
                shell.openExternal(url).catch(err =>
                    console.error('Failed to open external link via navigation:', err),
                );
            }
        });
    }

    private static loadMetricsContent(window: BrowserWindow): void {
        if (APP_ENVIRONMENT.IS_DEV && APP_ENVIRONMENT.VITE_DEV_SERVER_URL) {
            window.loadURL(`${APP_ENVIRONMENT.VITE_DEV_SERVER_URL}#/pipeline-metrics`);
        } else {
            window.loadFile(APP_PATHS.RENDERER_HTML, {hash: '/pipeline-metrics'});
        }
    }
}
