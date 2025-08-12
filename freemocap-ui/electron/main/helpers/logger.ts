import {app, BrowserWindow} from 'electron';
import {APP_ENVIRONMENT} from "./app-environment";
import {APP_PATHS} from "./app-paths";
import {exec} from "child_process";

export class LifecycleLogger {
  static logProcessInfo() {
    console.log(`
    ============================================
    Starting FreeMoCap Electron App v${app.getVersion()}
    \t- Environment: ${APP_ENVIRONMENT.IS_DEV ? 'Development' : 'Production'}
    \t- Platform: ${process.platform}-${process.arch}
    \t- Node: ${process.versions.node}
    \t- Chrome: ${process.versions.chrome}
    \t- Electron: ${process.versions.electron}
    \t- Python Auto-Start: ${APP_ENVIRONMENT.SHOULD_LAUNCH_PYTHON}
    ============================================`);
  }

  static logWindowCreation(win: BrowserWindow) {
    console.log(`
    [Window Manager] Created main window
    \t- ID: ${win.id}
    \t- DevTools: ${APP_ENVIRONMENT.IS_DEV ? 'Open' : 'Closed'}
    \t- Load URL: ${win.webContents.getURL()}`);
  }

  static logPythonProcess(pythonProcess:  ReturnType<typeof exec> ) {
    console.log(`
    [Python Server] Started external process
    \t- PID: ${pythonProcess.pid}
    \t- Command: ${pythonProcess.spawnargs.join(' ')}
    \t- Executable: ${pythonProcess.spawnfile}
    \t- Executable Path: ${APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH};
    \t- Environment: ${JSON.stringify(APP_ENVIRONMENT)}`);
  }

  static logIpcEvent(channel: string, sender: string) {
    console.log(`
    [IPC Event] ${new Date().toISOString()}
    \t- Channel: ${channel}
    \t- Origin: ${sender}`);
  }

  static logShutdownSequence() {
    console.log(`
    [Shutdown] Initiating termination sequence
    \t- Windows open: ${BrowserWindow.getAllWindows().length}
    \t- Python running: ${process.env.SKELLYCAM_SHOULD_SHUTDOWN === 'true' ? 'No' : 'Yes'}
    \t- Reason: Application closure requested`);
  }
}
