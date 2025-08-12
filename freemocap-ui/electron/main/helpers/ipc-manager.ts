import {app, dialog, ipcMain, shell} from 'electron';
import {WindowManager} from "./window-manager";
import {PythonServer} from "./python-server";
import path from "node:path";
import fs from "node:fs";

export class IpcManager {
    static initialize() {
        this.handleWindowControls();
        this.handlePythonControls();
        this.handleFileSystemControls();
    }

    private static handleWindowControls() {
        ipcMain.handle('open-child-window', (_, route) => {
            console.log('Opening child window with route:', route);
            const child = WindowManager.createMainWindow();
            child.loadURL(`${process.env.VITE_DEV_SERVER_URL}#${route}`);
        });
    }
    private static handleFileSystemControls() {
        ipcMain.handle('select-directory', async () => {
            const result = await dialog.showOpenDialog({
                properties: ['openDirectory']
            });

            if (!result.canceled && result.filePaths.length > 0) {
                return result.filePaths[0];
            }
            return null;
        });
        ipcMain.handle('open-folder', async (_, folderPath: string) => {
            try {
                await shell.openPath(folderPath);
                return true;
            } catch (error) {
                console.error('Failed to open folder:', error);
                return false;
            }
        });
        ipcMain.handle('get-home-directory', () => {
            return app.getPath('home');
        });


        ipcMain.handle('get-folder-contents', async (_, folderPath: string) => {
            try {
                // Ensure the folder exists
                if (!fs.existsSync(folderPath)) {
                    return { error: 'Folder does not exist', path: folderPath };
                }

                // Get all files and directories in the folder
                const entries = fs.readdirSync(folderPath);

                // Map the entries to include their details
                const contents = entries.map(entry => {
                    const fullPath = path.join(folderPath, entry);
                    try {
                        const stats = fs.statSync(fullPath);
                        return {
                            name: entry,
                            path: fullPath,
                            isDirectory: stats.isDirectory(),
                            isFile: stats.isFile(),
                            size: stats.size,
                            created: stats.birthtime,
                            modified: stats.mtime,
                            accessed: stats.atime
                        };
                    } catch (err) {
                        // If we can't get stats for some reason, just return basic info
                        return {
                            name: entry,
                            path: fullPath,
                            error: 'Failed to get file stats'
                        };
                    }
                });

                return {
                    path: folderPath,
                    contents: contents
                };
            } catch (error: any) {
                console.error('Failed to get folder contents:', error);
                return {
                    error: `Failed to get folder contents: ${error.message}`,
                    path: folderPath
                };
            }
        });
    }

    private static handlePythonControls() {
        ipcMain.handle('restart-python-server', () => {
            console.log('Restarting Python Server');
            PythonServer.shutdown();
            PythonServer.start();
        });
    }
}
