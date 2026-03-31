import { Menu, BrowserWindow, shell, app } from 'electron';
import path from 'node:path';
import os from 'node:os';

/**
 * Build and set the native application menu.
 * Call this once after the main window is created.
 */
export function buildAppMenu(mainWindow: BrowserWindow): void {
    const isMac = process.platform === 'darwin';

    const template: Electron.MenuItemConstructorOptions[] = [
        // macOS app menu
        ...(isMac ? [{
            label: app.name,
            submenu: [
                { role: 'about' as const },
                { type: 'separator' as const },
                {
                    label: 'Settings…',
                    click: () => sendNavigate(mainWindow, '/settings'),
                },
                { type: 'separator' as const },
                { role: 'services' as const },
                { type: 'separator' as const },
                { role: 'hide' as const },
                { role: 'hideOthers' as const },
                { role: 'unhide' as const },
                { type: 'separator' as const },
                { role: 'quit' as const },
            ],
        }] : []),

        // File
        {
            label: 'File',
            submenu: [
                isMac ? { role: 'close' as const } : { role: 'quit' as const },
            ],
        },

        // Edit
        {
            label: 'Edit',
            submenu: [
                { role: 'undo' as const },
                { role: 'redo' as const },
                { type: 'separator' as const },
                { role: 'cut' as const },
                { role: 'copy' as const },
                { role: 'paste' as const },
                { role: 'selectAll' as const },
            ],
        },

        // View
        {
            label: 'View',
            submenu: [
                { role: 'reload' as const },
                { role: 'forceReload' as const },
                { role: 'toggleDevTools' as const },
                { type: 'separator' as const },
                { role: 'resetZoom' as const },
                { role: 'zoomIn' as const },
                { role: 'zoomOut' as const },
                { type: 'separator' as const },
                { role: 'togglefullscreen' as const },
            ],
        },

        // Tools
        {
            label: 'Tools',
            submenu: [
                {
                    label: 'Settings…',
                    accelerator: isMac ? 'Cmd+Shift+S' : 'Ctrl+Shift+S',
                    click: () => sendNavigate(mainWindow, '/settings'),
                },
                { type: 'separator' as const },
                {
                    label: 'Open Config Folder',
                    click: () => {
                        const configDir = path.join(os.homedir(), '.freemocap');
                        shell.openPath(configDir);
                    },
                },
                {
                    label: 'Open Data Folder',
                    click: () => {
                        const dataDir = path.join(os.homedir(), 'freemocap_data');
                        shell.openPath(dataDir);
                    },
                },
            ],
        },

        // Window
        {
            label: 'Window',
            submenu: [
                { role: 'minimize' as const },
                { role: 'zoom' as const },
                ...(isMac ? [
                    { type: 'separator' as const },
                    { role: 'front' as const },
                ] : [
                    { role: 'close' as const },
                ]),
            ],
        },

        // Help
        {
            label: 'Help',
            submenu: [
                {
                    label: 'FreeMoCap Documentation',
                    click: () => shell.openExternal('https://freemocap.github.io/documentation/'),
                },
                {
                    label: 'GitHub Repository',
                    click: () => shell.openExternal('https://github.com/freemocap/freemocap'),
                },
                { type: 'separator' as const },
                {
                    label: 'Settings…',
                    click: () => sendNavigate(mainWindow, '/settings'),
                },
            ],
        },
    ];

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

/** Send a navigation request to the renderer process. */
function sendNavigate(window: BrowserWindow, route: string): void {
    if (window.isDestroyed()) return;
    window.webContents.send('navigate', route);
    window.focus();
}