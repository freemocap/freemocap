import { app, BrowserWindow } from 'electron';
import { exec } from 'child_process';

export class LifecycleLogger {
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
