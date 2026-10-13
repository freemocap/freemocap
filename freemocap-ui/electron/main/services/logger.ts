import {app, BrowserWindow} from 'electron';
import {exec} from 'child_process';
import {createWriteStream, mkdirSync} from 'node:fs';
import path from 'node:path';

export class LifecycleLogger {
    /** Development-only renderer console capture, readable without DevTools. */
    static saveRendererConsole(win: BrowserWindow) {
        try {
            const directory = path.join(app.getAppPath(), '.test-artifacts');
            mkdirSync(directory, {recursive: true});
            const logPath = path.join(directory, 'ui-console.log');
            const output = createWriteStream(logPath, {flags: 'a', encoding: 'utf8'});
            const capture = (event: Electron.Event<Electron.WebContentsConsoleMessageEventParams>) => {
                output.write(JSON.stringify({
                    timestamp: new Date().toISOString(),
                    level: event.level,
                    message: event.message,
                    source: event.sourceId,
                    line: event.lineNumber,
                }) + '\n');
            };
            output.on('error', error => {
                win.webContents.removeListener('console-message', capture);
                console.error('Could not write UI console log:', error);
            });
            win.webContents.on('console-message', capture);
            win.once('closed', () => output.end());
            output.write(JSON.stringify({timestamp: new Date().toISOString(), message: 'UI window opened', pid: process.pid}) + '\n');
            console.log(`UI console log: ${logPath}`);
        } catch (error) {
            console.error('Could not open UI console log:', error);
        }
    }

    static logProcessInfo() {
        console.log(`
    ============================================
    Starting FreeMoCap v${app.getVersion()}
    Platform: ${process.platform}-${process.arch}
    Node: ${process.versions.node}
    Chrome: ${process.versions.chrome}
    Electron: ${process.versions.electron}
    ============================================`);
    }

    static logWindowCreation(win: BrowserWindow) {
        console.log(`[Window Manager] Created window ID: ${win.id}`);
    }

    static logPythonProcess(pythonProcess: ReturnType<typeof exec>) {
        console.log(`[Python Server] Started process PID: ${pythonProcess.pid}`);
    }
}
