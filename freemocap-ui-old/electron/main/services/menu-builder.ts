// electron/main/services/menu-builder.ts
import { app, BrowserWindow, Menu, MenuItemConstructorOptions, shell } from 'electron';

// Channel name for menu-triggered actions sent to the renderer
const MENU_CHANNEL = 'menu-action';

export type MenuAction =
    | 'navigate-home'
    | 'navigate-cameras'
    | 'navigate-playback'
    | 'navigate-settings'
    | 'toggle-theme'
    | 'toggle-sidebar'
    | 'detect-cameras'
    | 'connect-cameras'
    | 'close-cameras'
    | 'pause-unpause-cameras'
    | 'start-recording'
    | 'stop-recording'
    | 'open-recording-folder'
    | 'toggle-fullscreen'
    | 'toggle-locale'
    | 'check-for-updates'
    | `change-locale:${string}`;

export interface LocaleEntry {
    code: string;
    label: string;
}

// All translatable menu label keys. Renderer sends these as a Record<MenuLabelKey, string>.
export interface MenuLabels {
    menuFile: string;
    menuView: string;
    menuCamera: string;
    menuRecording: string;
    menuHelp: string;
    menuDetectCameras: string;
    menuConnectCameras: string;
    menuCloseAllCameras: string;
    menuOpenRecordingFolder: string;
    menuToggleSidebar: string;
    menuToggleTheme: string;
    menuToggleFullScreen: string;
    menuPauseUnpause: string;
    menuConnectApplySettings: string;
    menuCloseAll: string;
    menuDocumentation: string;
    menuGitHubRepository: string;
    menuReportIssue: string;
    menuAbout: string;
    menuCheckForUpdates: string;
    menuPlayback: string;
    // Keys reused from the existing i18n
    home: string;
    cameras: string;
    settings: string;
    startRecording: string;
    stopRecording: string;
    language: string;
}

// English fallback labels used until the renderer sends translated ones
const DEFAULT_LABELS: MenuLabels = {
    menuFile: 'File',
    menuView: 'View',
    menuCamera: 'Camera',
    menuRecording: 'Recording',
    menuHelp: 'Help',
    menuDetectCameras: 'Detect Cameras',
    menuConnectCameras: 'Connect Cameras',
    menuCloseAllCameras: 'Close All Cameras',
    menuOpenRecordingFolder: 'Open Recording Folder…',
    menuToggleSidebar: 'Toggle Sidebar',
    menuToggleTheme: 'Toggle Theme',
    menuToggleFullScreen: 'Toggle Full Screen',
    menuPauseUnpause: 'Pause / Unpause',
    menuConnectApplySettings: 'Connect / Apply Settings',
    menuCloseAll: 'Close All',
    menuDocumentation: 'Documentation',
    menuGitHubRepository: 'GitHub Repository',
    menuReportIssue: 'Report an Issue…',
    menuAbout: 'About FreeMoCap',
    menuCheckForUpdates: 'Check for Updates…',
    menuPlayback: 'Playback',
    home: 'Home',
    cameras: 'Cameras',
    settings: 'Settings',
    startRecording: 'Start Recording',
    stopRecording: 'Stop Recording',
    language: 'Language',
};

function sendMenuAction(action: MenuAction): void {
    const window = BrowserWindow.getFocusedWindow();
    if (!window) return;
    window.webContents.send(MENU_CHANNEL, action);
}

const isMac = process.platform === 'darwin';

function buildLanguageSubmenu(t: MenuLabels, locales: LocaleEntry[], currentLocale: string): MenuItemConstructorOptions {
    return {
        label: t.language,
        submenu: [
            {
                label: 'Toggle Language',
                accelerator: 'CmdOrCtrl+Shift+L',
                click: () => sendMenuAction('toggle-locale'),
            },
            { type: 'separator' },
            ...locales.map((locale): MenuItemConstructorOptions => ({
                label: locale.label,
                type: 'radio',
                checked: locale.code === currentLocale,
                click: () => sendMenuAction(`change-locale:${locale.code}`),
            })),
        ],
    };
}

function buildFileMenu(t: MenuLabels, locales: LocaleEntry[], currentLocale: string): MenuItemConstructorOptions {
    return {
        label: t.menuFile,
        submenu: [
            {
                label: t.menuOpenRecordingFolder,
                accelerator: 'CmdOrCtrl+O',
                click: () => sendMenuAction('open-recording-folder'),
            },
            { type: 'separator' },
            buildLanguageSubmenu(t, locales, currentLocale),
            {
                label: `${t.settings}…`,
                accelerator: 'CmdOrCtrl+,',
                click: () => sendMenuAction('navigate-settings'),
            },
            { type: 'separator' },
            isMac
                ? { role: 'close' }
                : { role: 'quit' },
        ],
    };
}

function buildViewMenu(t: MenuLabels): MenuItemConstructorOptions {
    return {
        label: t.menuView,
        submenu: [
            {
                label: t.home,
                accelerator: 'CmdOrCtrl+1',
                click: () => sendMenuAction('navigate-home'),
            },
            {
                label: t.cameras,
                accelerator: 'CmdOrCtrl+2',
                click: () => sendMenuAction('navigate-cameras'),
            },
            {
                label: t.menuPlayback,
                accelerator: 'CmdOrCtrl+3',
                click: () => sendMenuAction('navigate-playback'),
            },
            { type: 'separator' },
            {
                label: t.menuToggleSidebar,
                accelerator: 'CmdOrCtrl+B',
                click: () => sendMenuAction('toggle-sidebar'),
            },
            {
                label: t.menuToggleTheme,
                accelerator: 'CmdOrCtrl+Shift+T',
                click: () => sendMenuAction('toggle-theme'),
            },
            { type: 'separator' },
            {
                label: t.menuToggleFullScreen,
                accelerator: isMac ? 'Ctrl+Cmd+F' : 'F11',
                click: () => sendMenuAction('toggle-fullscreen'),
            },
            { type: 'separator' },
            { role: 'reload' },
            { role: 'forceReload' },
            { role: 'toggleDevTools' },
            { type: 'separator' },
            { role: 'resetZoom' },
            { role: 'zoomIn' },
            { role: 'zoomOut' },
        ],
    };
}

function buildCameraMenu(t: MenuLabels): MenuItemConstructorOptions {
    return {
        label: t.menuCamera,
        submenu: [
            {
                label: t.menuDetectCameras,
                accelerator: 'CmdOrCtrl+D',
                click: () => sendMenuAction('detect-cameras'),
            },
            {
                label: t.menuConnectApplySettings,
                accelerator: 'CmdOrCtrl+Shift+C',
                click: () => sendMenuAction('connect-cameras'),
            },
            {
                label: t.menuCloseAll,
                accelerator: 'CmdOrCtrl+Shift+W',
                click: () => sendMenuAction('close-cameras'),
            },
            { type: 'separator' },
            {
                label: t.menuPauseUnpause,
                accelerator: 'Shift+Space',
                click: () => sendMenuAction('pause-unpause-cameras'),
            },
        ],
    };
}

function buildRecordingMenu(t: MenuLabels): MenuItemConstructorOptions {
    return {
        label: t.menuRecording,
        submenu: [
            {
                label: t.startRecording,
                accelerator: 'CmdOrCtrl+Shift+S',
                click: () => sendMenuAction('start-recording'),
            },
            {
                label: t.stopRecording,
                accelerator: 'CmdOrCtrl+Shift+X',
                click: () => sendMenuAction('stop-recording'),
            },
            { type: 'separator' },
            {
                label: t.menuOpenRecordingFolder,
                click: () => sendMenuAction('open-recording-folder'),
            },
        ],
    };
}

function buildHelpMenu(t: MenuLabels): MenuItemConstructorOptions {
    return {
        label: t.menuHelp,
        submenu: [
            {
                label: t.menuDocumentation,
                click: () => {
                    // Keep in sync with freemocap-ui/src/constants/external-urls.ts
                    shell.openExternal('https://docs.freemocap.org/freemocap');
                },
            },
            {
                label: t.menuGitHubRepository,
                click: () => {
                    shell.openExternal('https://github.com/freemocap/freemocap');
                },
            },
            {
                label: t.menuReportIssue,
                click: () => {
                    shell.openExternal('https://github.com/freemocap/freemocap/issues/new');
                },
            },
            { type: 'separator' },
            {
                label: 'FreeMoCap Foundation',
                click: () => {
                    shell.openExternal('https://freemocap.org');
                },
            },
            { type: 'separator' },
            {
                label: t.menuCheckForUpdates,
                click: () => sendMenuAction('check-for-updates'),
            },
            { type: 'separator' },
            {
                label: t.menuAbout,
                click: () => sendMenuAction('navigate-settings'),
            },
        ],
    };
}

export interface MenuBuildParams {
    labels?: Partial<MenuLabels>;
    locales?: LocaleEntry[];
    currentLocale?: string;
}

export function buildApplicationMenu(params: MenuBuildParams = {}): void {
    const { labels, locales = [], currentLocale = 'en' } = params;
    const t: MenuLabels = { ...DEFAULT_LABELS, ...labels };
    const template: MenuItemConstructorOptions[] = [];

    // macOS app menu
    if (isMac) {
        template.push({
            label: app.getName(),
            submenu: [
                { role: 'about' },
                { type: 'separator' },
                {
                    label: `${t.settings}…`,
                    accelerator: 'Cmd+,',
                    click: () => sendMenuAction('navigate-settings'),
                },
                { type: 'separator' },
                { role: 'services' },
                { type: 'separator' },
                { role: 'hide' },
                { role: 'hideOthers' },
                { role: 'unhide' },
                { type: 'separator' },
                { role: 'quit' },
            ],
        });
    }

    template.push(buildFileMenu(t, locales, currentLocale));
    template.push(buildViewMenu(t));
    template.push(buildCameraMenu(t));
    template.push(buildRecordingMenu(t));

    // macOS window menu
    if (isMac) {
        template.push({
            label: 'Window',
            submenu: [
                { role: 'minimize' },
                { role: 'zoom' },
                { type: 'separator' },
                { role: 'front' },
            ],
        });
    }

    template.push(buildHelpMenu(t));

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

export { MENU_CHANNEL };
