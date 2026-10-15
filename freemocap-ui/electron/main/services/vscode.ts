import {app, dialog, shell} from 'electron';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

// Registered handlers are best-effort availability, not proof of a successful launch.
// [@electronAppProtocol; @electronShellExternal]
export function isVSCodeAvailable(): boolean {
    return Boolean(app.getApplicationNameForProtocol('vscode://'));
}

// Preserve encoded spaces, Unicode, # and ? in local and UNC folder paths.
// VS Code's documented project URL format: [@vscodeCommandLine]
export function vscodeFolderURL(folderPath: string): string {
    if (!path.isAbsolute(folderPath)) throw new Error('Recording folder must be an absolute path.');
    const file = pathToFileURL(path.normalize(folderPath));
    const url = `vscode://file${file.host ? `//${file.host}` : ''}${file.pathname}`;
    if (process.platform === 'win32' && url.length > 2081) {
        throw new Error('The recording folder path is too long to open through a Windows URL handler.');
    }
    return url;
}

export async function openFolderInVSCode(folderPath: string): Promise<boolean> {
    try {
        const url = vscodeFolderURL(folderPath);
        if (!(await fs.stat(folderPath)).isDirectory()) throw new Error('The recording path is not a folder.');
        if (!isVSCodeAvailable()) throw new Error('No VS Code link handler was found.');
        await shell.openExternal(url);
        return true;
    } catch (error) {
        const {response} = await dialog.showMessageBox({
            type: 'info',
            title: 'Open in VS Code',
            message: 'FreeMoCap could not open this folder in VS Code.',
            detail: `${error instanceof Error ? error.message : String(error)}\n\nInstall and launch the desktop version of Visual Studio Code, then use Check again beside the playback button. If it is already installed, reinstalling may repair its link handler. Adding code to PATH alone does not register the link handler.`,
            buttons: ['Close', 'Download VS Code'],
            defaultId: 0,
            cancelId: 0,
        });
        if (response === 1) await shell.openExternal('https://code.visualstudio.com/download');
        return false;
    }
}
