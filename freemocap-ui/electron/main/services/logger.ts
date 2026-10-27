import {app, BrowserWindow} from 'electron';
import {exec} from 'child_process';
import fs from 'node:fs';
import path from 'node:path';

export class LifecycleLogger {
    private static pythonLogStream: fs.WriteStream | null = null;

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
        this.openPythonLogFile();
    }

    static getPythonServerLogPath(): string {
        return path.join(app.getPath('userData'), 'logs', 'python-server.log');
    }

    private static openPythonLogFile() {
        try {
            const logPath = this.getPythonServerLogPath();
            fs.mkdirSync(path.dirname(logPath), {recursive: true});
            this.pythonLogStream?.end();
            this.pythonLogStream = fs.createWriteStream(logPath, {flags: 'w'});
            this.pythonLogStream.on('error', (error) => {
                console.error('Python server log stream error:', error);
            });
            this.pythonLogStream.write(`=== Python server session started at ${new Date().toISOString()} ===\n`);
        } catch (error) {
            console.error('Failed to open Python server log file:', error);
            this.pythonLogStream = null;
        }
    }

    /**
     * Log a chunk of stdout/stderr from the Python server, both to the console
     * and to a persistent log file so the output survives even when the app
     * exits (or crashes) before the user can read the console.
     */
    static logPythonOutput(stream: 'stdout' | 'stderr', chunk: Buffer | string) {
        const text = chunk.toString();

        if (stream === 'stderr') {
            console.error(`[Python Server stderr] ${text}`);
        } else {
            console.log(`[Python Server stdout] ${text}`);
        }

        this.pythonLogStream?.write(`[${stream}] ${text}${text.endsWith('\n') ? '' : '\n'}`);
    }
}
