import {BrowserWindow, shell} from 'electron';
import {APP_PATHS} from "./app-paths";
import {APP_ENVIRONMENT} from "./app-environment";
import {LifecycleLogger} from "./logger";

export class WindowManager {
    static createMainWindow() {
        const window = new BrowserWindow({
            title: 'FreeMoCap 💀📸',
            icon: APP_PATHS.FREEMOCAP_ICON_PATH,
            width: 1280,
            height: 720,
            webPreferences: {
                preload: APP_PATHS.PRELOAD,
                contextIsolation: true,
                nodeIntegration: false
            }
        });

        this.configureWindowHandlers(window);
        this.loadContent(window);
        LifecycleLogger.logWindowCreation(window);
        return window;
    }

    private static configureWindowHandlers(window: BrowserWindow) {
        console.log('Configuring window handlers');
        window.on('closed', () => {
            console.log('Window closed');
        });
        window.webContents.on('did-finish-load', () => {
            console.log('Window finished loading');
            window.webContents.send('app-ready', Date.now());
        });

        window.webContents.setWindowOpenHandler(({url}) => {
            console.log('Opening window', url);
            if (url.startsWith('https:')) shell.openExternal(url);
            return {action: 'deny'};
        });
    }

    private static loadContent(window: BrowserWindow) {
        console.log('Loading app content - APP_ENVIRONMENT.IS_DEV:', APP_ENVIRONMENT.IS_DEV);

        APP_ENVIRONMENT.IS_DEV
            ? window.loadURL(process.env.VITE_DEV_SERVER_URL!)
            : window.loadFile(APP_PATHS.RENDERER_HTML);

        if (APP_ENVIRONMENT.IS_DEV) {
            // window.webContents.openDevTools();
        }
    }

}
